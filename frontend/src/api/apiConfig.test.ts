import { beforeEach, describe, expect, it } from 'vitest';
import { apiConfig, getRequestHeaders } from './apiConfig';

describe('apiConfig request headers', () => {
  beforeEach(() => {
    apiConfig.TOKEN = undefined;
    document.cookie = 'csrftoken=; Max-Age=0; path=/';
  });

  it('does not add CSRF headers to safe requests', async () => {
    document.cookie = 'csrftoken=safe-token; path=/';

    await expect(getRequestHeaders('GET')).resolves.not.toHaveProperty(
      'X-CSRFToken'
    );
  });

  it('adds CSRF headers to unsafe requests when the cookie exists', async () => {
    document.cookie = 'csrftoken=unsafe-token; path=/';

    await expect(getRequestHeaders('POST')).resolves.toMatchObject({
      'Content-Type': 'application/json',
      'X-CSRFToken': 'unsafe-token',
    });
  });

  it('omits bearer auth when the SPA has no in-memory token', async () => {
    document.cookie = 'csrftoken=unsafe-token; path=/';

    await expect(getRequestHeaders('PATCH')).resolves.not.toHaveProperty(
      'Authorization'
    );
  });
});
