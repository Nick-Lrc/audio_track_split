import subprocess
import argparse
import traceback
from collections import defaultdict
import json
import os, os.path
import datetime

FILE_TAGS = {'file', 'start', 'end', 'tracks'}
INVALID_CHARACTERS = {
    '<': '‹', 
    '>': '›', 
    ':': '：', 
    '"': '\'', 
    '/': '／', 
    '\\': '＼', 
    '|': '∣', 
    '?': '？', 
    '*': '＊'
}

# https://en.wikipedia.org/wiki/Cue_sheet_(computing)
# https://www.gnu.org/software/ccd2cue/manual/html_node/CUE-sheet-format.html#CUE-sheet-format
class CueParser():
    def __init__(self, offset='00:00:00.00'):
        self._clear()
        self.offset = offset

    def info(self):
        if not self._info:
            self._info = self._disc.copy()
            self._info['tracks'] = []
            for track in self._tracks:
                self._info['tracks'].append(track.copy())
        return self._info

    def parse(self, doc):
        self._clear()
        self._parse_disc(doc)
        line = self._readline(doc)
        self._parse_track_tag(line)
        while line:
            line = self._parse_track(doc)
        self._complete_endings()
        self._get_unique_titles()

    def _parse_disc(self, doc):
        line = self._readline(doc)
        while line and not self._parse_file_tag(line):
            if not self._parse_comment_tag(self._disc, line):
                self._parse_tag(self._disc, line)
            line = self._readline(doc)

    def _parse_track(self, doc):
        line = self._readline(doc)
        while line and not self._parse_track_tag(line):
            if not self._parse_index_tag(line):
                if not self._parse_comment_tag(self._tracks[-1], line):
                    self._parse_tag(self._tracks[-1], line)
            line = self._readline(doc)
        return line

    def _parse_index_tag(self, line):
        fields = line.split(maxsplit=2)
        if len(fields) == 3 and fields[0] == 'INDEX':
            timestamp = convert_timestamp(fields[2], offset=self.offset)
            if fields[1] == '01':
                return self._parse_tag(self._tracks[-1], f'START {timestamp}')
            elif len(self._tracks) - 2 >= 0:
                return self._parse_tag(self._tracks[-2], f'END {timestamp}')
        return False

    def _parse_track_tag(self, line):
        fields = line.split(maxsplit=2)
        if len(fields) == 3 and fields[0] == 'TRACK':
            track = defaultdict(str)
            self._tracks.append(track)
            return self._parse_tag(track, line.rpartition(' ')[0])
        return False

    def _parse_file_tag(self, line):
        fields = line.split(maxsplit=1)
        if len(fields) == 2 and fields[0] == 'FILE':
            return self._parse_tag(self._disc, line.rpartition(' ')[0])
        return False

    def _parse_comment_tag(self, target, line):
        fields = line.split(maxsplit=2)
        if len(fields) == 3 and fields[0] == 'REM':
            return self._parse_tag(target, ' '.join(fields[1:]))
        return False

    def _parse_tag(self, target, line):
        fields = line.split(maxsplit=1)
        if len(fields) == 2:
            target[fields[0].lower()] = fields[1].strip('\'"')
            return True
        return False

    def _complete_endings(self):
        if len(self._tracks) > 1:
            for i in range(len(self._tracks) - 1):
                if 'end' not in self._tracks[i]:
                    self._tracks[i]['end'] = self._tracks[i + 1]['start']

    def _get_unique_titles(self):
        titles = defaultdict(int)
        for track in self._tracks:
            title = track['title']
            if title in titles:
                if 'performer' in track:
                    title = f'{title} ({track["performer"]} ver.)'
                    track['title'] = title
                else:
                    track['title'] = f'{title} (ver. {titles[title]})'
            titles[title] += 1

    def _readline(self, doc):
        return doc.readline().strip()

    def _clear(self):
        self._disc = defaultdict(str)
        self._tracks = []
        self._info = None

def cut_video(src, dst, disc, track, options):
    params = [
        'ffmpeg',
        '-y',
        '-ss', track['start']
    ]

    if 'end' in track:
        params += ['-to', track['end']]

    params += [
        '-i', src,
    ]

    metadata = track.copy()
    for key, val in disc.items():
        if key not in track:
            metadata[key] = val
    for key in FILE_TAGS:
        if key in metadata:
            del metadata[key]
    metadata['track'] = f'{int(metadata["track"])}/{len(disc["tracks"])}'
    metadata['album'] = disc['title']
    if 'artist' not in metadata and 'performer' in metadata:
        metadata['artist'] = metadata['performer']
    if 'album_artist' not in metadata and 'performer' in disc:
        metadata['album_artist'] = disc['performer']

    for key, val in metadata.items():
        params += [
            '-metadata', f'{key}={val}'
        ]

    if options.audio_codec:
        params += ['-c:a', options.audio_codec]
    params += [dst]
    subprocess.run(params)

def convert_timestamp(timestamp, format='%M:%S:%f', offset='00:00:00.00'):
    original = datetime.datetime.strptime(timestamp, format)
    base = datetime.datetime.strptime('00:00:00', format)
    diff = datetime.datetime.strptime(offset, '%H:%M:%S.%f')
    return (original + (diff - base)).strftime('%H:%M:%S.%f')

def replace_invalid_characters(title):
    for character in INVALID_CHARACTERS:
        title = title.replace(character, INVALID_CHARACTERS[character])
    return title.strip()

def options():
    parser = argparse.ArgumentParser(description='Split audio tracks')
    parser.add_argument('-i', '--input', type=str, help='input CUE sheet')
    parser.add_argument('-o', '--output', type=str, default='.', help='output directory')
    parser.add_argument('--audio-format', type=str, default='flac', help='output audio format')
    parser.add_argument('--audio-codec', type=str, default=None, help='output audio codec')
    parser.add_argument('--text-encoding', type=str, default='mbcs', help='text encoding')
    parser.add_argument('--offset', type=str, default='00:00:00.00', help='track offset')
    return parser.parse_args()

if __name__ == "__main__":
    options = options()
    if not os.path.exists(options.output):
        os.makedirs(options.output)
    
    # https://docs.python.org/3/library/codecs.html#standard-encodings
    document = open(options.input, 'r', encoding=options.text_encoding)
    cue = CueParser(offset=options.offset)
    cue.parse(document)

    for track in cue.info()['tracks']:
        src = os.path.join(os.path.split(options.input)[0], cue.info()["file"])
        dst = os.path.join(options.output, f'{replace_invalid_characters(track["title"])}.{options.audio_format}')
        cut_video(src, dst, cue.info(), track, options)
