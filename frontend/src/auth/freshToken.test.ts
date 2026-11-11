import { describe, expect, it, vi } from 'vitest'

import { expiresSoon, freshTokenGetter } from './freshToken'

function tokenExpiringAt(exp: number) {
  const payload = btoa(JSON.stringify({ exp }))
    .replace(/=+$/, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
  return `header.${payload}.signature`
}

const now = () => Math.floor(Date.now() / 1000)

describe('expiresSoon', () => {
  it('passes a token with time left', () => {
    expect(expiresSoon(tokenExpiringAt(now() + 3600))).toBe(false)
  })

  it('flags an expired token or one about to expire', () => {
    expect(expiresSoon(tokenExpiringAt(now() - 60))).toBe(true)
    expect(expiresSoon(tokenExpiringAt(now() + 10))).toBe(true)
  })

  it('leaves alone a token with no readable expiry', () => {
    expect(expiresSoon('not-a-token')).toBe(false)
    expect(expiresSoon(`h.${btoa('{}')}.s`)).toBe(false)
  })
})

describe('freshTokenGetter', () => {
  it('returns a good token without refreshing', async () => {
    const good = tokenExpiringAt(now() + 3600)
    const refresh = vi.fn()
    const get = freshTokenGetter(async () => good, refresh)
    expect(await get()).toBe(good)
    expect(refresh).not.toHaveBeenCalled()
  })

  it('refreshes an expired token once for requests that arrive together', async () => {
    let stored = tokenExpiringAt(now() - 60)
    const fresh = tokenExpiringAt(now() + 3600)
    const refresh = vi.fn(async () => {
      stored = fresh
    })
    const get = freshTokenGetter(async () => stored, refresh)
    expect(await Promise.all([get(), get(), get()])).toEqual([fresh, fresh, fresh])
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('still answers when the refresh fails', async () => {
    const expired = tokenExpiringAt(now() - 60)
    const get = freshTokenGetter(
      async () => expired,
      vi.fn().mockRejectedValue(new Error('offline')),
    )
    expect(await get()).toBe(expired)
    const throwsAtOnce = freshTokenGetter(
      async () => expired,
      () => {
        throw new Error('not ready')
      },
    )
    expect(await throwsAtOnce()).toBe(expired)
  })

  it('leaves signed-out requests alone', async () => {
    const refresh = vi.fn()
    expect(await freshTokenGetter(async () => undefined, refresh)()).toBeUndefined()
    expect(refresh).not.toHaveBeenCalled()
  })
})
