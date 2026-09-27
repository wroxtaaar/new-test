import test from 'node:test';
import assert from 'node:assert/strict';
import { getRetryLabel, shouldRetryLink } from '../src/retryQueue.ts';
import { isTeraboxUrl, extractSurl } from '../server/terabox.ts';

test('retry decisions disable retries and fail immediately', () => {
  assert.equal(shouldRetryLink(0, 1), false);
  assert.equal(shouldRetryLink(1, 1), false);
});

test('retry labels include the file name and retry number', () => {
  assert.equal(
    getRetryLabel({ fileNames: ['report.zip'], retryCount: 2, maxRetries: 5, url: 'https://example.com' }),
    'report.zip (retry 2/5)'
  );
});

test('TeraBox links are detected and normalized', () => {
  assert.equal(isTeraboxUrl('https://terabox.com/s/1abc123xyz'), true);
  assert.equal(isTeraboxUrl('https://1024tera.com/sharing/link?surl=abc123xyz'), true);
  assert.equal(extractSurl('https://terabox.com/s/abc123xyz'), 'abc123xyz');
});

