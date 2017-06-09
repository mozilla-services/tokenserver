import os

if "MOZSVC_SQLURI" not in os.environ:
    os.environ["MOZSVC_SQLURI"] = "sqlite:////tmp/tokenserver.db"
