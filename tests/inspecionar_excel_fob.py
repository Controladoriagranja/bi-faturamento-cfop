"""Atalho de inspe??o read-only para o leitor reutiliz?vel do m?dulo FOB."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from fob.workbook import main

if __name__=='__main__':main()
