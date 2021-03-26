import subprocess
import argparse
import traceback
from collections import defaultdict
import json
import os, os.path
import datetime

FILE_TAGS = {'file', 'start', 'end', 'tracks'}

# https://en.wikipedia.org/wiki/Cue_sheet_(computing)
class CueParser():
    def __init__(self):
        self._clear()

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
            timestamp = convert_timestamp(fields[2])
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

    def _readline(self, doc):
        return doc.readline().strip()

    def _clear(self):
        self._disc = defaultdict(str)
        self._tracks = []
        self._info = None

def cut_video(src, dst, disc, track):
    params = [
        'ffmpeg',
        '-y',
        '-ss', track['start']
    ]

    if 'end' in track:
        params += ['-to', track['end']]

    params += [
        '-i', src,
        # '-c', 'copy', 
        # '-copyts'
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

    for key, val in metadata.items():
        params += [
            '-metadata', f'{key}={val}'
        ]

    params += [dst]
    subprocess.run(params)

def convert_timestamp(timestamp, format='%M:%S:%f'):
    return datetime.datetime.strptime(timestamp, format).strftime('%H:%M:%S.%f')

def options():
    parser = argparse.ArgumentParser(description='Split audio tracks')
    parser.add_argument('-i', '--input', type=str, help='input CUE sheet')
    parser.add_argument('-o', '--output', type=str, default='.', help='output directory')
    parser.add_argument('--audio-encoding', type=str, default='flac', help='output audio encoding')
    parser.add_argument('--text-encoding', type=str, default='mbcs', help='text encoding')
    return parser.parse_args()

if __name__ == "__main__":
    options = options()
    if not os.path.exists(options.output):
        os.makedirs(options.output)
    
    # https://docs.python.org/3/library/codecs.html#standard-encodings
    document = open(options.input, 'r', encoding=options.text_encoding)
    cue = CueParser()
    cue.parse(document)

    for track in cue.info()['tracks']:
        dst = os.path.join(options.output, f'{track["title"]}.{options.audio_encoding}')
        cut_video(cue.info()["file"], dst, cue.info(), track)
