from dataclasses import dataclass
import os
import pickle
from pathlib import Path
from typing import Dict, List


# from fastapi.params import Header
from all_uvicorn_modules import *
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response


# region For unpickling
@dataclass
class PostEntry:
    request_data: bytes
    response_data: bytes
    mime_type: str


@dataclass
class GetEntry:
    mime_type: str
    data: str
# endregion


app = FastAPI()
SERVER_DATA_FILENAME = 'server_data.pickle'
MAIN_PATH = Path("static")

with open(SERVER_DATA_FILENAME, "rb") as server_data_file:
    server_data = pickle.load(server_data_file)

get_entries: Dict[str, GetEntry] = server_data['get_entries']
post_entries: Dict[str, List[PostEntry]] = server_data['post_entries']


@app.get('/{file_path:path}')
async def webapp(file_path: str):
    if file_path == '':
        file_path = 'index.html'

    # Normalize
    file_path = str(Path(file_path))

    if file_path in get_entries:
        entry = get_entries[file_path]

        return Response(entry.data, headers={'Content-Type': entry.mime_type})
    else:
        raise HTTPException(status_code=404, detail=f'No File Path: {file_path}')


@app.post('/{file_path:path}')
async def post_webapp(file_path: str, request: Request):
    path = Path() / file_path
    if str(path) not in post_entries:
        raise HTTPException(status_code=404, detail=f'File "{file_path}" not found.')

    body = await request.body()
    post_req = [req for req in post_entries[file_path]
                if req.request_data == body]

    if not post_req:
        print('data not found:', body)
        raise HTTPException(status_code=404, detail='No response exists for given content')

    post_req = post_req[0]

    return Response(post_req.response_data, headers={'mimeType': post_req.mime_type,
                                                     'Content-Type': post_req.mime_type})


if __name__ == '__main__':
    config_kwargs = dict(app=app,
                         host='0.0.0.0',
                         port=int(os.getenv('PORT', 80)),
                         #  workers=1,
                         log_level='info',
                         )
    uvicorn.run(**config_kwargs)
