import logging
import os
import sys
from typing import TextIO, Optional, Sequence

import click
from cytoolz import take

from ghostwriter import __version__
from ghostwriter.model import LanguageModel
from ghostwriter.text import CharacterTokenizer, documents_from_text_files


class LanguageModelParamType(click.ParamType):
    name = "language-model"

    def convert(self, path: str, _, __) -> LanguageModel:
        try:
            return LanguageModel.load(path)
        except ValueError as e:
            self.fail(e)


@click.group("ghostwriter")
@click.version_option(version=__version__)
@click.option("--log", type=click.Choice(["debug", "info", "warning", "error", "critical"]), default="info",
              help="Logging level (default info)")
def ghostwriter(log: str):
    """
    Machine assisted writing
    """
    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", level=getattr(logging, log.upper()))


@ghostwriter.command("train", short_help="train model")
@click.argument("data", type=click.File(), nargs=-1)
@click.option("--model", type=click.Path(), help="directory in which to save the model")
@click.option("--context-size", default=10, help="context size (default 10)")
@click.option("--hidden", default=256, help="LSTM hidden units (default 256)")
@click.option("--dropout", default=0.2, help="dropout rate (default 0.2)")
@click.option("--epochs", default=10, help="number of training epochs (default 10)")
@click.option("--progress-bar/--no-progress-bar", default=True, help="show progress bar (default True)")
def train_command(data: Sequence[TextIO], model: Optional[str], context_size: int, hidden: int, dropout: float,
                  epochs: int, progress_bar: bool):
    """
    Train a language model.
    """
    if model is not None and os.path.exists(model):
        try:
            language_model = LanguageModel.load(model)
        except ValueError as e:
            sys.exit(e)
    else:
        tokenizer = CharacterTokenizer.create_from_documents(documents_from_text_files(data), context_size)
        language_model = LanguageModel.create(tokenizer, hidden, dropout)
        if model is None:
            logging.warning("Not saving a model.")
        else:
            language_model.save(model)
    history = language_model.train(documents_from_text_files(data), epochs, model, progress_bar)
    logging.info(f"{history.iterations} iterations, final loss {history.final_loss:0.5f}")


@ghostwriter.command("perplexity", short_help="calculate perplexity")
@click.argument("model", type=LanguageModelParamType())
@click.argument("data", type=click.File(), nargs=-1)
def perplexity_command(model: LanguageModel, data: Sequence[TextIO]):
    """
    Calculate test set perplexity with a language model.
    """
    perplexity = model.perplexity(documents_from_text_files(data))
    print(f"{perplexity:0.4f}")


@ghostwriter.command("generate", short_help="generate text")
@click.argument("model", type=LanguageModelParamType())
@click.argument("seed", type=str)
@click.option("--characters", default=200, help="number of characters to generate (default 200)")
def generate_command(model: LanguageModel, seed: str, characters: int):
    """
    Generate text from a model.
    """
    sys.stdout.write(seed)
    for character in take(characters, (str(token) for token in model.generate(list(seed)) if not token.is_meta)):
        sys.stdout.write(character)
    print()


def main():
    ghostwriter(auto_envvar_prefix="GHOSTWRITER")
