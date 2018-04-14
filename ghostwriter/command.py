import logging
import os
import sys
from typing import TextIO, Optional

import click

from ghostwriter import Codec, characters, LanguageModel, __version__


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
@click.argument("data", type=click.File())
@click.option("--model", type=click.Path(), help="directory in which to save the model")
@click.option("--context-size", default=10, help="context size (default 10)")
@click.option("--hidden", default=256, help="LSTM hidden units (default 256)")
@click.option("--dropout", default=0.2, help="dropout rate (default 0.2)")
@click.option("--epochs", default=10, help="number of training epochs (default 10)")
@click.option("--n", type=int, help="limit data to this many characters")
def train_command(data: TextIO, model: Optional[str], context_size: int, hidden: int, dropout: float,
                  epochs: int, n: Optional[int]):
    """
    Train a language model.
    """
    codec = Codec(characters(data, n))
    if model is not None and os.path.exists(model):
        try:
            language_model = LanguageModel.load(model)
        except ValueError as e:
            sys.exit(e)
    else:
        if model is None:
            logging.warning("Not saving a model.")
        language_model = LanguageModel.create(hidden, context_size, dropout, codec, model)
    history = language_model.train(characters(data, n), epochs, model)
    logging.info(f"{len(history.history['loss'])} iterations, final loss {history.history['loss'][-1]:0.5f}")


@ghostwriter.command("perplexity", short_help="calculate perplexity")
@click.argument("model", type=LanguageModelParamType())
@click.argument("data", type=click.File())
@click.option("--n", type=int, help="limit data to this many characters")
def perplexity_command(model: LanguageModel, data: TextIO, n: Optional[int]):
    """
    Calculate test set perplexity with a language model.
    """
    perplexity = model.perplexity(characters(data, n))
    print(f"{perplexity:0.4f}")


def main():
    ghostwriter(auto_envvar_prefix="GHOSTWRITER")
