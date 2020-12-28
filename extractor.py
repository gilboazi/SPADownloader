from dataclasses import dataclass
from base64 import b64encode, b64decode
from pathlib import Path, PurePath
import re
from typing import Any, Dict, List, Set, Tuple, Union
import argparse
import json
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen
import pickle


@dataclass
class PostEntry:
    request_data: bytes
    response_data: bytes
    mime_type: str


@dataclass
class GetEntry:
    mime_type: str
    data: bytes


GetEntries = Dict[str, GetEntry]
PostEntries = Dict[str, List[PostEntry]]


def get_args() -> Tuple[str, str]:
    parser = argparse.ArgumentParser(description="Create a mock web server from a HAR file.")

    parser.add_argument("input_file", help="The name of the input HAR file.")
    parser.add_argument("--url", default=None, help="The root endpoint URL.")

    args = parser.parse_args()

    return args.input_file, args.url or input("--url not supplied.\nEnter the root endpoint URL:")


def get_content_data_from_text(content: dict) -> bytes:
    content_data = content['text']
    if not content_data:
        err_msg = "'text-content' in HAR File is EMPTY! - Configure Browser to Allow Large Network Requests Logging (in Dev-Tools). Firefox is awesome doing this..."
        fix_msg = "In Firefox: Enter in URL: 'about:config', then set 'devtools.netmonito.responseBodyLimit' to 104857600 (or another larger number)"
        raise ValueError(f'{err_msg}\n{fix_msg}')
    if content.get("encoding") == "base64":
        try:
            return b64decode(content_data)
        except:
            pass

    return content_data.encode()


def get_content_data_from_entry(response, url):
    content = response.get("content")

    if not content:
        return None

    response_size = content.get("size")

    status = response.get("status")

    if "text" in content and status and status != 204:
        return get_content_data_from_text(content)
    else:
        if response_size == 0:
            return None
        try:
            with urlopen(url) as response:
                return response.read()
        except URLError:
            print('CHECK INTERNET CONNECTION')
            raise


def is_url_the_root_index(url: Union[bytes, str], root_url: str, har_data: dict):
    if isinstance(url, bytes):
        url = url.decode()

    return url.lower() in [root_url.lower(), har_data['log']['pages'][0]['title'].lower()]


def convert_relative_to_domain(content: bytes, domain: str) -> bytes:
    new_data = re.sub(br'(src|href|content)=\"(/\w+/.+?\")( |>)',
                      f'\\1="/{domain}\\2\\3'.encode(),
                      content)
    return new_data


def log_shit(data):
    def f(inp):
        print(inp.group(2))
        return b"/" + inp.group(2)

    return f


def replace_domains_to_relative_static_paths(get_entries: Dict[str, GetEntry], post_entries: Dict[str, List[PostEntry]], all_domains: Set[str]):
    domains_re = '|'.join([re.escape(d) for d in all_domains])
    replace_domain_pattern = re.compile(fr"(https?:)?//({domains_re})".encode())

    for get_entry in get_entries.values():
        get_entry.data = replace_domain_pattern.sub(log_shit(br'/\2'), get_entry.data)
        get_entry.data = get_entry.data.replace(b"https://", b"http://")

    for post_entry_list in post_entries.values():
        for post_entry in post_entry_list:
            post_entry.response_data = replace_domain_pattern.sub(log_shit(br'/\3'), post_entry.response_data)
            post_entry.response_data = post_entry.response_data.replace(b"https://", b"http://")


def copy_root_paths_to_root(entries: Dict[str, Any], root_path: PurePath):
    """ 
    Copy all files that are relative to the root path to the application root.
    For example: if root path is "e.com/f/g", will copy files like "e.com/f/g/example" to "/example".
    """

    # list() because the dictionary changes and we have to make the iterable permanent
    for file_path_str, entry in list(entries.items()):
        file_path = PurePath(file_path_str)

        # Should use relative_to if upgrading to 3.9
        if str(file_path).startswith(str(root_path)):
            path_without_root = str(file_path.relative_to(root_path))

            # Copy to root as well
            entries[path_without_root] = entry


def parse_entries(har_data: dict, root_url: str) -> Tuple[GetEntries, PostEntries]:
    entries = har_data["log"]["entries"]
    all_domains = set()
    get_entries = {}
    post_entries = {}
    print(root_url)
    parsed_root_url = urlparse(root_url)
    root_path = PurePath(parsed_root_url.netloc + parsed_root_url.path)

    for entry in entries:
        request = entry.get('request')
        if not request:
            continue

        url = request.get('url')
        method = request.get('method')

        if not method or not url or 'localhost' in url:
            continue

        parsed_url = urlparse(url)
        path = Path(parsed_url.path)

        domain = parsed_url.netloc
        all_domains.add(domain)

        response = entry.get("response")
        if not response:
            continue

        content = get_content_data_from_entry(response, url)
        if content is None:
            continue

        mime_type = response["content"].get("mimeType", "text/html")

        if method == "GET":
            get_entry = GetEntry(mime_type, content)

            filename = path.name.strip('/\\')
            dirname = str(path.parent).strip('/\\')

            if mime_type == "text/html":
                if dirname == "" and filename == "" and is_url_the_root_index(url, root_url, har_data):
                    filename = "index.html"
                else:
                    # The original code saves a file with a hash in case the dir and filename are both empty.
                    # However, I think it never accesses it later, so I skipped this part.
                    pass

                content = convert_relative_to_domain(content, domain)

            if is_url_the_root_index(url, root_url, har_data):
                get_entries["index.html"] = get_entry

            file_path = PurePath(domain) / dirname / filename
            get_entries[str(file_path)] = get_entry
        elif method == "POST" and 'postData' in request:
            request_path = str(path).replace('\\', '/')
            post_entries.setdefault(str(request_path), []).append(PostEntry(request['postData'], content, mime_type))

    replace_domains_to_relative_static_paths(get_entries, post_entries, all_domains)
    copy_root_paths_to_root(get_entries, root_path)
    copy_root_paths_to_root(post_entries, root_path)

    return get_entries, post_entries


def export_to_file(get_entries: Dict[str, GetEntry], post_entries: Dict[str, List[PostEntry]]):
    result = {
        "get_entries": get_entries,
        "post_entries": post_entries
    }

    with open("server_data.pickle", "wb") as result_file:
        pickle.dump(result, result_file)


def main():
    har_filename, root_url = get_args()

    with open(har_filename, "rb") as har_file:
        har_data = json.load(har_file)

    get_entries, post_entries = parse_entries(har_data, root_url)

    export_to_file(get_entries, post_entries)


if __name__ == "__main__":
    main()
