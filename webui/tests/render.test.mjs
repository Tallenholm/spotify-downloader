import test from 'node:test';
import assert from 'node:assert/strict';
import {
  explicitLabel,
  albumCard,
  formatDuration,
  trackTable,
  queueRail,
  downloadRail,
} from '../out/assets/ui.js';

test('explicit status is unmistakable', () => assert.equal(explicitLabel('explicit'), 'E  EXPLICIT'));
test('non-explicit is not mislabeled clean', () => assert.equal(explicitLabel('non_explicit'), 'NO EXPLICIT CONTENT'));
test('duration renders as music time', () => assert.equal(formatDuration(201), '3:21'));
test('album card exposes exact edition and download action', () => {
  const html = albumCard({album_id:'abc123',name:'Album',artists:['Artist'],artist_ids:[],release_date:'2026-01-01',total_tracks:12,explicit_track_count:4,non_explicit_track_count:8,explicit_status:'explicit',edition_tags:['Explicit','Deluxe'],spotify_url:'https://open.spotify.com/album/abc123',tracks:[],sibling_album_ids:[],grouping_confidence:1});
  assert.match(html, /E  EXPLICIT/);
  assert.match(html, /data-download-album="abc123"/);
  assert.match(html, /Deluxe/);
});

test('album track table communicates strict policy without inventing confidence', () => {
  const html = trackTable([
    {track_id:'t1',name:'DNA.',artists:['Kendrick Lamar'],duration:185,track_number:2,disc_number:1,explicit:true,spotify_url:'https://open.spotify.com/track/t1'},
    {track_id:'t2',name:'YAH.',artists:['Kendrick Lamar'],duration:160,track_number:3,disc_number:1,explicit:false,spotify_url:'https://open.spotify.com/track/t2'},
  ], 'explicit_only');
  assert.match(html, /SOURCE POLICY/);
  assert.match(html, /STRICT EXPLICIT/);
  assert.match(html, /Resolve on download/);
  assert.doesNotMatch(html, /98%/);
});

test('queue rail exposes real queue state and exact track counts', () => {
  const html = queueRail([{
    job_id:'job1',kind:'album',source_id:'album1',title:'DAMN.',content_preference:'explicit_only',state:'downloading',created_at:'2026-08-10T00:00:00Z',updated_at:'2026-08-10T00:00:00Z',tracks:[
      {job_track_id:'jt1',job_id:'job1',track_id:'t1',name:'BLOOD.',artists:['Kendrick Lamar'],spotify_url:'x',explicit:true,position:1,duration:118,track_number:1,disc_number:1,state:'completed'},
      {job_track_id:'jt2',job_id:'job1',track_id:'t2',name:'DNA.',artists:['Kendrick Lamar'],spotify_url:'y',explicit:true,position:2,duration:185,track_number:2,disc_number:1,state:'downloading'},
    ]
  }]);
  assert.match(html, /DOWNLOAD QUEUE/);
  assert.match(html, /1\/2 complete/);
  assert.match(html, /DNA\./);
  assert.match(html, /Downloading/);
});

test('bottom rail is download status, not fake playback chrome', () => {
  const html = downloadRail([], 'explicit_only');
  assert.match(html, /EXPLICIT ONLY/);
  assert.match(html, /No active downloads/);
  assert.doesNotMatch(html, /play/i);
});