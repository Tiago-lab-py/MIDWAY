import sys
import os
sys.path.insert(0, os.path.abspath(r'D:\MIDWAY'))

from midway.api.routes.iqs import download_geracao_iqs

try:
    download_geracao_iqs("2a0a2df3")
except Exception as e:
    import traceback
    traceback.print_exc()
