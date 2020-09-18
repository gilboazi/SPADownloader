python_version=$(python -V | awk '{print $2}')
if ! [[ "$python_version" =~ 3.7 ]]; then
    echo "Python Version Must Be 3.7"
    return
fi

# python -m venv venv
venv/scripts/python -m pip install -r requirements.txt
# MUST uninstall uvicorn and pydantic and reinstall it WITHOUT BINARY:
venv/scripts/python -m pip uninstall uvicorn pydantic -y
venv/scripts/python -m pip install uvicorn --no-binary uvicorn
venv/scripts/python -m pip install pydantic --no-binary pydantic
venv/scripts/pyinstaller --onefile --clean --distpath . server.py
venv/scripts/pyinstaller --onefile --clean --distpath . extracter.py
