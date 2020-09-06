import sys

if not sys.version_info > (2, 7):
    print("Python 2 is no more supported")
    exit(-1)
elif not sys.version_info >= (3, 8):
    print("Requires at least python 3.8 (using dataclasses and walrus operator)")
    exit(-1)

import dataclasses
from dataclasses import dataclass
from typing import List
from datetime import datetime
import argparse
from pathlib import Path
import git
import re
import copy
import json
from jinja2 import Environment, FileSystemLoader

import pprint

PATTERN_TIL_ENTRY_FILE = re.compile(".*\\.(md|adoc)")
PATTERN_TIL_ENTRY_RENAME = re.compile("^(.*) => (.*)$")
PATTERN_TIL_ENTRY_MOVE = re.compile("^{(.*) => (.*)}(.*)$")
PATTERN_TIL_ENTRY_TITLE = re.compile("^= (.*)$")

@dataclass
class TILTimeline:
    created: datetime
    updated: datetime

@dataclass
class TILEntry:
    title: str
    link: str
    created: datetime
    updated: datetime

@dataclass
class TILTopic:
    title: str
    anchor: str
    count: int
    entries: List[TILEntry]

@dataclass
class TILInfos:
    count: int
    topics: List[TILTopic]

def update_til_entry_path(til_timeline, old, new):
    til_timeline[new] = copy.deepcopy(til_timeline[old])
    return new

def create_til_timeline(repo_path, ref='master'):
    til_timeline = {}
    repo = git.Repo(repo_path, odbt=git.GitDB)
    commits = reversed(list(repo.iter_commits(ref)))
    for commit in commits:
        dt = commit.committed_datetime
        files = list(commit.stats.files.keys())
        for file_path in files:
            if match_file := PATTERN_TIL_ENTRY_FILE.match(file_path):
                if match_move := PATTERN_TIL_ENTRY_MOVE.match(file_path):
                    til_entry_path = update_til_entry_path(til_timeline,
                        old = match_move.group(1)+match_move.group(3),
                        new = match_move.group(2)+match_move.group(3))
                elif match_rename := PATTERN_TIL_ENTRY_RENAME.match(file_path):
                    til_entry_path = update_til_entry_path(til_timeline,
                        old = match_rename.group(1),
                        new = match_rename.group(2))
                else:
                    til_entry_path = file_path
                if til_entry_path not in til_timeline:
                    til_timeline[til_entry_path] = TILTimeline(created=dt, updated=dt)
                else:
                    til_timeline[til_entry_path].updated = dt
    return til_timeline

def prepare_til_infos(git_repo_path, til_timeline):
    til_infos = TILInfos(count=0, topics=[])
    topics = (topic for topic in Path(git_repo_path).iterdir() if topic.is_dir() and not topic.name.startswith('.'))
    for topic in topics:
        til_topic = TILTopic(title=topic.name, anchor=topic.name.lower(), count=0, entries=[])
        til_infos.topics.append(til_topic)
        entries = (entry for entry in topic.iterdir() if PATTERN_TIL_ENTRY_FILE.match(entry.name))
        for entry in entries:
            with open(entry, 'r') as f:
                line = f.readline()
                if match_entry_title := PATTERN_TIL_ENTRY_TITLE.match(line):
                    title = match_entry_title.group(1)
                else:
                    continue
            link=str(entry.relative_to(topic.parent))
            til_entry = TILEntry(title=title, link=link, created=til_timeline[link].created.date().isoformat(), updated=til_timeline[link].updated.date().isoformat())
            til_topic.entries.append(til_entry)
            til_topic.count += 1
            til_infos.count += 1
    return dataclasses.asdict(til_infos)

def render_readme_template(git_repo_path, template, til_infos):
    jinja2env = Environment(loader=FileSystemLoader(searchpath=git_repo_path))
    readme_template = jinja2env.get_template(template)
    return readme_template.render(til=til_infos)

def generate_readme(git_repo_path, template, output):
    til_timeline = create_til_timeline(git_repo_path)
    til_infos = prepare_til_infos(git_repo_path, til_timeline)
    with open(output, 'w') as f:
        f.write(render_readme_template(git_repo_path, template, til_infos))

def main():
    git_repo_path = Path(__file__).parent.resolve()

    parser = argparse.ArgumentParser(description='Generate README')
    parser.add_argument('--tmpl', metavar='template', type=str, help='name of the template')
    parser.add_argument('--out', metavar='output', type=str, help='name of the README file')
    args = parser.parse_args()

    generate_readme(git_repo_path, args.tmpl, args.out)

if __name__ == "__main__":
    main()
