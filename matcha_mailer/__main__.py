"""`python -m matcha_mailer <comando>`: vedi cli.py. Senza comando mostra l'elenco dei comandi."""

import sys

from matcha_mailer.cli import build_parser, main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        build_parser().print_help()
