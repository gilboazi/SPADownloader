import os
import json
from pathlib import Path

# from fastapi.params import Header
from all_uvicorn_modules import *
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
MAIN_PATH = Path('static')
POST_DATA_FILENAME = 'post_data.json'
try:
    POST_DATA_MAP = json.loads(Path(POST_DATA_FILENAME).read_text())
except:
    POST_DATA_MAP = {}



@app.get('/{file_path:path}')
async def webapp(file_path: str):
    if file_path == '':
        file_path = 'index.html'
    if file_path.startswith('static'):
        file = Path(file_path)
    else:
        file = MAIN_PATH / file_path
    if file.is_file():
        headers = None
        with file.open('rb') as fh:
            first_line = fh.read(20)
            if b'<!DOCTYPE html>' in first_line:
                headers = {'Content-Type': 'text/html'}
                return StreamingResponse(file.open('rb'), headers=headers)
        return StreamingResponse(file.open('rb'))
    else:
        # return {'msg': f'No File Path: {file_path}'}
        raise HTTPException(status_code=404, detail=f'No File Path: {file_path}')

@app.post('/{file_path:path}')
async def post_webapp(file_path: str, request: Request):
    file_path = '/' + file_path
    if file_path not in POST_DATA_MAP:
        raise HTTPException(status_code=404, detail=f'File "{file_path}" not found.')

    body = await request.body()
    post_req = [req for req in POST_DATA_MAP[file_path]
                if req['postData']['text'].encode() == body]
    if not post_req:
        print('data not found:', body)
        raise HTTPException(status_code=404, detail='No Response Waiting for Given Content')

    post_req = post_req[0]
    file = Path(post_req['resp']['file_on_disk'])
    if file.is_file():
        return StreamingResponse(file.open('rb'),
        headers={
            'mimeType': post_req['resp']['mime_type'],
            'Content-Type': post_req['resp']['mime_type'],
        })
    else:
        print(f'ERROR filepath "{file_path}" doesn\'t exist!')

    raise HTTPException(status_code=500, detail='Internal Error, Unexpected Response. (data on post-request saved in file, but the actual file-response was not saved.')


if __name__ == '__main__':
    config_kwargs = dict(app=app,
                         host='0.0.0.0',
                         port=int(os.getenv('PORT', 80)),
                        #  workers=1,
                         log_level='info',
                        )
    uvicorn.run(**config_kwargs)