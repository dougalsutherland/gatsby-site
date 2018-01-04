#!/usr/bin/env python
from __future__ import unicode_literals

import argparse
from copy import copy
import datetime
import io
import os
import re
import subprocess

from ruamel.yaml import YAML
import staticjinja
from unidecode import unidecode


_dir = os.path.abspath(os.path.dirname(__file__))


def paper_data():
    with io.open(os.path.join(_dir, "papers.yaml")) as f:
        return YAML().load(f)


filters = {}
def filter(fn):
    filters[fn.__name__] = fn
    return fn


@filter
def venue_url(venue, year=None):
    if 'web_by_year' in venue and year in venue['web_by_year']:
        return venue['web_by_year'][year]
    elif 'web' in venue:
        return venue['web']
    return None


@filter
def get_author(author, coauthors):
    is_equal = author.endswith('*')
    if is_equal:
        author = author[:-1]
    d = copy(coauthors[author])
    d['is_equal'] = is_equal
    return d

@filter
def get_paper(key, papers):
    return next(paper for paper in papers if paper['key'] == key)

translation_table = {}
@filter
def latex_escape(string):
    "Turn unicode accented characters into LaTeX escapes."
    # based on https://stackoverflow.com/a/4579006/344821
    global translation_table

    if not translation_table:
        p = re.compile(r'%?.*\DeclareUnicodeCharacter\{(\w+)\}\{(.*)\}')
        fn = subprocess.check_output(['kpsewhich', 'utf8enc.dfu']).strip()
        with io.open(fn) as f:
            for line in f:
                m = p.match(line)
                if m:
                    codepoint, latex = m.groups()
                    latex = latex.replace('@tabacckludge', '')
                    translation_table[int(codepoint, 16)] = '{' + latex + '}'

    return string.translate(translation_table)


filters['unidecode'] = unidecode


@filter
def full_name(author_dict):
    if 'full_name' in author_dict:
        return author_dict['full_name']
    return '{} {}'.format(author_dict['first'], author_dict['last'])


@filter
def last_name(author_dict):
    return author_dict['last']


@filter
def first_name(author_dict):
    return author_dict['first']


@filter
def first_inits(author_dict):
    def init(x):
        return '-'.join(n[0] for n in x.split('-'))
    return ' '.join(init(n) for n in author_dict['first'].split())


@filter
def bibtex_authors(authors, coauthors, mark_equal=''):
    auths = []
    for a in authors:
        auth = get_author(a, coauthors)
        name = latex_escape(full_name(auth))
        auths.append(name + (mark_equal if auth['is_equal'] else ''))
    return ' and '.join(auths)


@filter
def bibtex_key(paper, coauthors):
    auth = get_author(paper['authors'][0], coauthors)
    prefix = unidecode(last_name(auth)).lower()
    return '{}:{}'.format(prefix, paper['key'])


@filter
def maybe_wrap(content, before, after):
    if content:
        return "{}{}{}".format(before, content, after)
    else:
        return ""


@filter
def maybe_link(content, url=None):
    if url:
        return "<a href={}>{}</a>".format(url, content)
    else:
        return content


@filter
def last_edit_dt(filenames):
    # is the file currently edited in git?
    fs = list(filenames)
    try:
        subprocess.check_output(
            ['git', 'diff-index', '--quiet', 'HEAD'] + fs, cwd=_dir)
    except subprocess.CalledProcessError:
        return datetime.datetime.now()
    else:
        out = subprocess.check_output(
            ['git', 'log', '-1', '--format=%ct'] + fs, cwd=_dir)
        return datetime.datetime.fromtimestamp(int(out.strip()))


def make_site():
    site = staticjinja.make_site(
        contexts=[('.*', paper_data)],
        filters=filters,
    )
    site._env.tests['falsey'] = lambda x: not x
    return site


def render(site, files=None, watch=False):
    if files:
        for file in files:
            site.render_template(site.get_template(file))
    else:
        site.render(use_reloader=watch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true', default=False)
    parser.add_argument('files', nargs='*')
    args = parser.parse_args()

    site = make_site()
    render(site, files=args.files, watch=args.watch)
