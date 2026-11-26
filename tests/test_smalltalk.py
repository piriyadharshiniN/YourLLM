import asyncio
import unittest
from unittest.mock import patch

import config
import server
from src.rag_pipeline import NO_DOCS, RAGPipeline, is_small_talk


SMALL_TALK_EXAMPLES = {
    "greeting": (
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "hiya", "yo",
    ),
    "how_are_you": ("how are you", "how's it going", "what's up", "how do you do"),
    "thanks": ("thanks", "thank you", "thx", "ty", "thanks a lot", "appreciate it"),
    "acknowledgement": ("ok", "okay", "k", "cool", "got it", "alright", "great",
                        "nice", "sure", "fine"),
    "goodbye": ("bye", "goodbye", "see you", "see ya", "take care", "good night", "later"),
    "identity": ("who are you", "what can you do", "help"),
}

SOURCE_CHUNK = {
    "text": "Seaborn is a data visualization library.",
    "source": "guide.pdf",
    "page": 1,
    "doc_id": "doc-1",
    "score": 0.9,
}


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def embed_query(self, query):
        self.calls.append(query)
        return [0.1]


class FakeStore:
    def __init__(self, results=None):
        self.results = results or []
        self.calls = []

    def search(self, embedding, top_k, doc_ids):
        self.calls.append((embedding, top_k, doc_ids))
        return self.results


class FakeLLM:
    def __init__(self):
        self.rewrite_calls = []
        self.stream_calls = []

    def rewrite_question(self, question, history):
        self.rewrite_calls.append((question, history))
        return question

    def stream_answer(self, question, chunks, history, extra, temperature):
        self.stream_calls.append((question, chunks, history, extra, temperature))
        yield "Answer from the documents."


def make_pipeline(results=None, llm=None):
    pipeline = RAGPipeline.__new__(RAGPipeline)
    pipeline.embedder = FakeEmbedder()
    pipeline.store = FakeStore(results)
    pipeline._llm = llm or FakeLLM()
    return pipeline


def consume(response):
    async def read_body():
        return [part async for part in response.body_iterator]

    return asyncio.run(read_body())


class SmallTalkPipelineTests(unittest.TestCase):
    def test_examples_return_replies_without_retrieval_or_llm(self):
        for category, examples in SMALL_TALK_EXAMPLES.items():
            for question in examples:
                with self.subTest(category=category, question=question):
                    pipeline = make_pipeline()
                    events = list(pipeline.ask({"doc_ids": []}, question, []))

                    self.assertEqual([event["type"] for event in events],
                                     ["sources", "token"])
                    self.assertEqual(events[0]["sources"], [])
                    self.assertTrue(events[1]["text"])
                    self.assertNotIn("could not find", events[1]["text"].lower())
                    self.assertNotIn("source:", events[1]["text"].lower())
                    self.assertEqual(pipeline.embedder.calls, [])
                    self.assertEqual(pipeline.store.calls, [])
                    self.assertEqual(pipeline._llm.rewrite_calls, [])
                    self.assertEqual(pipeline._llm.stream_calls, [])

    def test_normalization_and_common_typos(self):
        for question in ("  HII!!! ", "  HELLO     ", "thankyou", "OKAYY...",
                         "WHAT'S up??", "hi 😊"):
            with self.subTest(question=question):
                pipeline = make_pipeline()
                self.assertTrue(is_small_talk(question))
                events = list(pipeline.ask({"doc_ids": []}, question, []))
                self.assertEqual(events[0], {"type": "sources", "sources": []})
                self.assertEqual(pipeline.embedder.calls, [])
                self.assertEqual(pipeline._llm.stream_calls, [])

    def test_greeting_mentions_attached_document_count(self):
        pipeline = make_pipeline()
        events = list(pipeline.ask({"doc_ids": ["one", "two"]}, "hello", []))
        self.assertIn("2 files", events[1]["text"])

    def test_small_talk_works_without_api_key_or_llm_initialization(self):
        pipeline = make_pipeline([SOURCE_CHUNK])
        pipeline._llm = None
        with patch.object(config, "GEMINI_API_KEY", ""):
            events = list(pipeline.ask({"doc_ids": ["doc-1"]}, "thanks", []))
        self.assertEqual(events[0], {"type": "sources", "sources": []})
        self.assertNotIn(NO_DOCS, events[1]["text"])
        self.assertEqual(pipeline.embedder.calls, [])
        self.assertEqual(pipeline.store.calls, [])

    def test_mixed_pleasantries_and_questions_use_retrieval(self):
        questions = (
            "hi, summarize my document",
            "ok what is seaborn?",
            "thanks, compare them",
        )
        for question in questions:
            with self.subTest(question=question):
                pipeline = make_pipeline([SOURCE_CHUNK])
                events = list(pipeline.ask({"doc_ids": ["doc-1"]}, question, []))

                self.assertEqual(events[0]["sources"], [SOURCE_CHUNK])
                self.assertEqual(events[1]["text"], "Answer from the documents.")
                self.assertEqual(len(pipeline.embedder.calls), 1)
                self.assertEqual(len(pipeline.store.calls), 1)
                self.assertEqual(len(pipeline._llm.stream_calls), 1)

    def test_mixed_question_without_documents_uses_normal_no_docs_flow(self):
        pipeline = make_pipeline()
        events = list(pipeline.ask({"doc_ids": []}, "ok what is seaborn?", []))
        self.assertFalse(is_small_talk("ok what is seaborn?"))
        self.assertEqual(events[0], {"type": "sources", "sources": []})
        self.assertEqual(events[1], {"type": "token", "text": NO_DOCS})
        self.assertEqual(len(pipeline.embedder.calls), 1)


class SmallTalkTitleTests(unittest.TestCase):
    def test_small_talk_keeps_new_chat_title_until_first_real_question(self):
        chat = {"id": "test-chat", "title": "New chat", "doc_ids": [], "messages": []}

        class FakeRag:
            def ask(self, chat, question, history):
                yield {"type": "sources", "sources": []}
                yield {"type": "token", "text": "Document answer."}

        with (
            patch.object(server, "_chat_or_404", return_value=chat),
            patch.object(server.storage, "get_chat", return_value=chat),
            patch.object(server.storage, "save_chat"),
            patch.object(server, "get_rag", return_value=FakeRag()) as get_rag,
        ):
            response = server.ask("test-chat", server.AskBody(question="hi"))
            self.assertEqual(chat["title"], "New chat")
            consume(response)
            self.assertEqual(chat["messages"][0]["content"], "hi")
            self.assertEqual(chat["messages"][1]["role"], "assistant")
            get_rag.assert_not_called()

            response = server.ask(
                "test-chat", server.AskBody(question="Summarize the report"))
            self.assertEqual(chat["title"], "Summarize the report")
            consume(response)
            get_rag.assert_called_once()


if __name__ == "__main__":
    unittest.main()
