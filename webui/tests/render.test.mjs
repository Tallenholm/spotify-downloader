import test from 'node:test';
import assert from 'node:assert/strict';
import { explicitLabel, albumCard, formatDuration } from '../out/assets/ui.js';

test('explicit status is unmistakable', () => assert.equal(explicitLabel('explicit'), 'E  EXPLICIT'));
test('non-explicit is not mislabeled clean', () => assert.equal(explicitLabel('non_explicit'), 'NO EXPLICIT CONTENT'));
test('duration renders as music time', () => assert.equal(formatDuration(201), '3:21'));
test('album card exposes exact edition and download action', () => {
  const html = albumCard({album_id:'abc123',name:'Album',artists:['Artist'],artist_ids:[],release_date:'2026-01-01',total_tracks:12,explicit_track_count:4,non_explicit_track_count:8,explicit_status:'explicit',edition_tags:['Explicit','Deluxe'],spotify_url:'https://open.spotify.com/album/abc123',tracks:[],sibling_album_ids:[],grouping_confidence:1});
  assert.match(html, /E  EXPLICIT/);
  assert.match(html, /data-download-album="abc123"/);
  assert.match(html, /Deluxe/);
});
