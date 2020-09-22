## Release-Versions:
### In releases-folder.

## To Compile By Your Self:
#### installation:
python-version==3.7
#### Just Run ./install.sh

#### commands in ./install.sh:
1. python -m venv venv
2. venv/scripts/python -m pip install -r requirements.txt
3. MUST uninstall uvicorn and pydantic and reinstall it WITHOUT BINARY:
4. venv/scripts/python -m pip uninstall uvicorn pydantic -y
5. venv/scripts/python -m pip install uvicorn --no-binary uvicorn
6. venv/scripts/python -m pip install pydantic --no-binary pydantic
7. venv/scripts/pyinstaller extracter.py --onefile --clean --distpath .
8. venv/scripts/pyinstaller server.py --onefile --clean --distpath .


