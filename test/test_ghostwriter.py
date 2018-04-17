import os
import unittest
from collections import Iterator
from typing import Sequence, Callable

import spacy
from click.testing import CliRunner
from spacy.language import Language

from ghostwriter.command import ghostwriter
from ghostwriter.model import LanguageModel
from ghostwriter.text import characters_from_text_files, GloVeCodec, TokenCodec, \
    labeled_words_in_sentences_language_model_data, CharacterTokenizer, SentenceTokenizer, Token

KAFKA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kafka.txt")


class TestGhostwriter(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_train_and_perplexity(self):
        with self.runner.isolated_filesystem():
            self.assert_command(ghostwriter, ["train", KAFKA, "--model=model", "--epochs=2"])
            model = LanguageModel.load("model")
            self.assertIsInstance(model, LanguageModel)
            self.assert_command(ghostwriter, ["perplexity", "model", KAFKA])
            self.assert_command(ghostwriter, ["generate", "model", "The quick brown "])

    def assert_command(self, command: Callable, arguments: Sequence[str], expected_exit_code: int = 0):
        result = self.runner.invoke(command, arguments, catch_exceptions=False)
        self.assertEqual(expected_exit_code, result.exit_code, result.output)


class TestTokenCodec(unittest.TestCase):
    def setUp(self):
        self.codec = TokenCodec.create_from_tokens(list("the red balloon"))

    def test_vocabulary_size(self):
        self.assertEqual(13, self.codec.vocabulary_size)

    def test_stringification(self):
        self.assertEqual("TokenCodec: vocabulary size 13", repr(self.codec))
        self.assertEqual("TokenCodec: vocabulary size 13", str(self.codec))

    def test_encode_decode(self):
        encoded = self.codec.encode(list("red"))
        self.assertIsInstance(encoded, Iterator)
        decoded = self.codec.decode(encoded)
        self.assertIsInstance(encoded, Iterator)
        self.assertEqual(["r", "e", "d"], list(decoded))

    def test_encode_decode_with_unknown(self):
        encoded = self.codec.encode(list("zed"))
        self.assertIsInstance(encoded, Iterator)
        decoded = self.codec.decode(encoded)
        self.assertIsInstance(encoded, Iterator)
        self.assertEqual([self.codec.OOV, "e", "d"], list(decoded))


class TestWordCodec(unittest.TestCase):
    def setUp(self):
        self.nlp = load_spacy_model()
        self.codec = GloVeCodec(self.nlp.vocab, 10000)

    def test_stringification(self):
        self.assertEqual("GloVeCodec: vocabulary size 10002", repr(self.codec))
        self.assertEqual("GloVeCodec: vocabulary size 10002", str(self.codec))

    def test_encode_decode(self):
        encoded = list(self.codec.encode(self.nlp("The quick brown fox.")))
        self.assertEqual(5, len(encoded))
        decoded = list(self.codec.decode(encoded))
        self.assertEqual(["The", "quick", "brown", "fox", "."], decoded)

    def test_embedding_matrix(self):
        self.assertEqual((10002, 300), self.codec.embedding_matrix.shape)


class TestTokenizer(unittest.TestCase):
    def setUp(self):
        self.nlp = load_spacy_model()

    def test_character_tokenizer(self):
        codec = TokenCodec.create_from_tokens("blue")
        pad = codec.PAD
        tokenizer = CharacterTokenizer(codec, 3)
        expected = [
            ((pad, pad, pad), "f"),
            ((pad, pad, "f"), "l"),
            ((pad, "f", "l"), "u"),
            (("f", "l", "u"), "e"),
            (("l", "u", "e"), pad),
            (("u", "e", pad), pad),
            (("e", pad, pad), pad)
        ]
        actual = list(tokenizer.from_text("flue"))
        self.assertEqual(expected, actual)

    def test_sentence_tokenizer(self):
        tokenizer = SentenceTokenizer(self.nlp, 3, 10000)
        pad = tokenizer.codec.PAD
        eos = Token.meta("-EOS-")
        expected = [
            ((pad, pad, pad), "The"),
            ((pad, pad, "The"), "blue"),
            ((pad, "The", "blue"), "fox"),
            (("The", "blue", "fox"), "ran"),
            (("blue", "fox", "ran"), eos),
            (("fox", "ran", eos), pad),
            (("ran", eos, pad), pad),
            ((eos, pad, pad), pad),
        ]
        actual = list(tokenizer.from_text("The blue fox ran", self.nlp))
        self.assertEqual(expected, actual)


class TestReadData(unittest.TestCase):
    def setUp(self):
        self.nlp = load_spacy_model()
        with open(KAFKA) as f:
            self.kakfa = self.nlp(f.read())

    def test_characters_from_text_file(self):
        kafka = open(KAFKA)
        s1 = list(characters_from_text_files([kafka]))
        s2 = list(characters_from_text_files([kafka]))
        self.assertEqual(s1, s2)
        kafka.close()

    def test_labeled_words_in_sentences_language_model_data(self):
        codec = GloVeCodec(self.nlp.vocab, 10000, {"-EOS-"})
        vectors, labels = labeled_words_in_sentences_language_model_data(codec, self.kakfa, 10)
        self.assertEqual((152, 10, 1), vectors.shape)
        self.assertEqual((152, 10003), labels.shape)


class TestModel(unittest.TestCase):
    def test_stringification(self):
        model = LanguageModel.create(256, 10, 0.2,
                                     TokenCodec.create_from_tokens(
                                         list("The quick brown fox jumps over the lazy dog.")))
        self.assertEqual("Language Model: 256 hidden nodes, TokenCodec: vocabulary size 31", repr(model))


model_singleton = {}


def load_spacy_model(name: str = "en_core_web_lg") -> Language:
    global model_singleton
    if name not in model_singleton:
        model_singleton[name] = spacy.load(name)
    return model_singleton[name]
