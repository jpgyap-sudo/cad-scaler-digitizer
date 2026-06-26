import { useEffect, useState } from 'react';

/**
 * Detects when a newer frontend build has been deployed while the current
 * tab stayed open. Vite emits a content-hashed main bundle (e.g.
 * /assets/index-Bmm9b_te.js) referenced from index.html. A long-lived SPA
 * tab keeps running its original bundle forever — re-uploading a file is an
 * in-app action that never re-fetches index.html — so users silently run
 * stale code after a deploy (this caused "I can't edit materials" / "my
 * change does nothing" confusion that was actually just a cached bundle).
 *
 * Strategy: capture the bundle filename this tab booted with, then on tab
 * focus / visibility (and a slow interval) re-fetch index.html with
 * cache:'no-store' and compare. If the referenced bundle changed, a new
 * version is live. We surface it as a dismissible banner rather than
 * force-reloading, so an in-progress edit isn't lost.
 */
function currentBundleHref(): string | null {
  const el = document.querySelector(
    'script[type="module"][src*="/assets/index-"]'
  ) as HTMLScriptElement | null;
  return el?.getAttribute('src') ?? null;
}

async function deployedBundleHref(): Promise<string | null> {
  try {
    const res = await fetch('/', { cache: 'no-store' });
    if (!res.ok) return null;
    const html = await res.text();
    const m = html.match(/\/assets\/index-[^"']+\.js/);
    return m ? m[0] : null;
  } catch {
    return null;
  }
}

export function useAppVersion(): { updateAvailable: boolean } {
  const [updateAvailable, setUpdateAvailable] = useState(false);

  useEffect(() => {
    const booted = currentBundleHref();
    // If we can't identify our own bundle (e.g. dev server), do nothing.
    if (!booted) return;

    let cancelled = false;

    const check = async () => {
      if (cancelled || document.visibilityState !== 'visible') return;
      const live = await deployedBundleHref();
      if (!cancelled && live && live !== booted) {
        setUpdateAvailable(true);
      }
    };

    const onVisible = () => {
      if (document.visibilityState === 'visible') check();
    };

    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', check);
    // Slow poll as a backstop for tabs that stay focused for a long time.
    const interval = window.setInterval(check, 120_000);
    check();

    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', check);
      window.clearInterval(interval);
    };
  }, []);

  return { updateAvailable };
}
