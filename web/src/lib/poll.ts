/** Refresh a REST endpoint on mount and every `ms` while the tab is visible.
 *
 * The leaderboard and top-games endpoints are plain REST — nothing pushes them
 * over the websocket — so the pages that show them run a timer. A hidden tab
 * polls nothing and catches up the moment it comes back, so a browser left
 * open on a background tab is not asking for rankings all night.
 *
 * Returns the stop function; `onMount(() => poll(load))` is the usual call.
 */
export function poll(load: () => void, ms = 30000): () => void {
  load();
  const timer = setInterval(() => {
    if (!document.hidden) load();
  }, ms);
  const onVisible = () => {
    if (!document.hidden) load(); // whatever we have went stale while away
  };
  document.addEventListener('visibilitychange', onVisible);
  return () => {
    clearInterval(timer);
    document.removeEventListener('visibilitychange', onVisible);
  };
}
