import base64
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from json import dumps, loads
from pathlib import Path
from typing import Dict, Union
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen
# from uuid import uuid4


STATIC_PATH = Path('static')
POST_DATA_JSON_MAP = Path('post_data.json')
shutil.rmtree(STATIC_PATH, ignore_errors=True)
input_har_file = Path(input('Enter Input HAR File: ').strip(' /\"\''))
if not input_har_file.is_file():
    raise ValueError(f'Invalid Path "{str(input_har_file)}"')
data = loads(input_har_file.read_bytes().decode())

all_urls = []
all_entries = []
post_entries = []

good_entries = []
error_entries = []
all_domains = []

entries = data['log']['entries']

def replace_https_to_http(content: bytes):
    if isinstance(content, str):
        content = content.encode()
    return content.replace(b'https://', b'http://')

INDEX_URL = input('Enter ROOT URL: ').lower().strip()
ROOT_DOMAIN = replace_https_to_http(INDEX_URL).decode().replace('http://', '').strip('/\\').lower()

@dataclass(init=False)
class ReqResp:
    url: str
    domain: str
    path: str
    method: str
    postData: Dict[str, str]  # Union['mimeType', 'text']
    filename: str
    dir: str
    mime_type: str
    content: Union[str, bytes]
    file_on_disk: str
    respSize: int

def out_temp(data: bytes, filepath: str = 'temp.txt'):
    if isinstance(data, str):
        data = data.encode()
    Path(filepath).write_bytes(data)

def convert_relative_to_domain(content: bytes, domain: str, prefix: str = 'static') -> str:
    new_data, num_subs = re.subn(r'(src|href|content)=\"(/\w+/.+?\")( |>)'.encode(),
                                    f'\\1="/{prefix}/{domain}\\2\\3'.encode(),
                                    content)
    return new_data, num_subs

def get_domain_from_url(content: bytes):
    valid_domain = r'(?:(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,6}'
    match = re.search(f'https?://(?P<domain>{valid_domain})'.encode(), content)
    if match:
        return match.group('domain').decode()

def save_deps_to_files():
    for entry in entries:
        resp = ReqResp()
        resp.url = entry['request']['url']
        resp.method = entry['request']['method']
        if resp.method == 'POST' and 'postData' in entry['request']:
            resp.postData = entry['request']['postData']
            post_entries.append(resp)
        all_urls.append(resp.url)
        if 'localhost' in resp.url:
            continue
        parsed_url = urlparse(resp.url)
        path = Path(parsed_url.path)
        resp.domain = parsed_url.netloc
        if resp.domain not in all_domains:
            all_domains.append(resp.domain)
        resp.path = str(path).replace('\\', '/')
        resp.filename = path.name.strip('/\\')
        resp.dir = str(path.parent).strip('/\\')
        resp.mime_type = entry['response']['content']['mimeType']
        resp.respSize = entry['response']['content']['size']

        if 'text' in entry['response']['content']:
            resp_content = entry['response']['content']['text']
            if not resp_content:
                err_msg = "'text-content' in HAR File is EMPTY! - Configure Browser to Allow Large Network Requests Logging (in Dev-Tools. Firefox is Awesome doint this..."
                fix_msg = "In Firefox: Enter in URL: 'about:config', then set 'devtools.netmonito.responseBodyLimit' to 104857600 (or another larger number)"
                raise ValueError(f'{err_msg}\n{fix_msg}')
            if entry['response']['content'].get('encoding') == 'base64':
                try:
                    resp.content = base64.b64decode(resp_content)
                except:
                    resp.content = resp_content.encode()
            else:
                resp.content = resp_content.encode()
        else:
            if resp.respSize == 0:
                continue
            try:
                with urlopen(resp.url) as response:
                    resp.content = response.read()
            except URLError:
                print('CHECK INTERNET CONNECTION')
                raise
        all_entries.append(resp)
        try:
            new_dir = STATIC_PATH / resp.domain / resp.dir
            new_file = new_dir / resp.filename
            if not new_dir.is_dir():
                os.makedirs(str(new_dir))
            if resp.method == 'GET':
                if resp.dir == '' and resp.filename == '':
                    if resp.mime_type == 'text/html' and is_url_the_root_index(resp.url):
                        new_file = new_dir / 'index.html'
                    else:
                        new_file = new_dir / get_hash(resp.url)[:4]
            else:
                new_file = new_dir / (get_hash(resp.url)[:4] + f'-sizeResp-{resp.respSize}' + get_hash(resp.content)[:4])
            if resp.mime_type == 'text/html':
                new_data, _ = convert_relative_to_domain(resp.content, resp.domain, prefix='static')
                resp.content = new_data

            new_file.write_bytes(resp.content)
            resp.file_on_disk = str(new_file)
            good_entries.append(resp)
        except Exception as e:
            print(f'resp -> {resp}')
            print(f'e -> {e}')
            error_entries.append(resp)

def replace_domains_to_relative_static_paths():
    domains_re = '|'.join([re.escape(d) for d in all_domains])
    replace_domain_pattern_re = re.compile(f"(https?:)?(//|\\/\\/)({domains_re})".encode())

    for file in STATIC_PATH.glob('**/*'):
        if not file.is_file():
            continue
        data: bytes = file.read_bytes()
        new_data, _ = replace_domain_pattern_re.subn('/static/\\3'.encode(), data)
        new_data = replace_https_to_http(new_data)
        file.write_bytes(new_data)

def save_post_requests():
    post_req_map = {}
    for entry in post_entries:
        if hasattr(entry, 'postData'):
            post_req_map.setdefault(entry.path, []).append({
                'postData': entry.postData,
                'resp': {
                    'file_on_disk': entry.file_on_disk,
                    'mime_type': entry.mime_type,
                }
            })
    Path(POST_DATA_JSON_MAP).write_text(json.dumps(post_req_map))

def copy_recursively(src_dir: Path, dst_dir: Path):
    for file in src_dir.glob('*'):
        if file.is_file():
            shutil.copyfile(file, dst_dir / file.name)
        elif file.is_dir():
            if file.name == dst_dir.name:
                copy_recursively(file, dst_dir)
            else:
                new_dst_dir = dst_dir / file.name
                if new_dst_dir.exists():
                    import sys
                    print('Duplicate Directories Trying to copy to Static-Folder. Open Issue if this happends.', file=sys.stderr)
                    sys.exit(1)
                shutil.copytree(file, new_dst_dir)

def is_url_the_root_index(url: str):
    if isinstance(url, bytes):
        url = url.decode()
    return url in [INDEX_URL, data['log']['pages'][0]['title']]

def get_hash(data: bytes, type='md5'):
    hash_type = type
    if isinstance(data, str):
        data = data.encode()
    return getattr(hashlib, hash_type)(data).hexdigest()

save_deps_to_files()
save_post_requests()
replace_domains_to_relative_static_paths()

copy_recursively((STATIC_PATH / ROOT_DOMAIN), STATIC_PATH)

for resp in all_entries:
    if is_url_the_root_index(resp.url):
        shutil.copyfile(resp.file_on_disk, STATIC_PATH / 'index.html')
        break




