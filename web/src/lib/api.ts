/** Thin fetch wrapper for the REST endpoints in API.md.
 *
 * Errors come back as `{"error": reason}` with a 4xx status; surface the
 * reason as the thrown Error's message so pages can show it verbatim.
 */
export async function api(
  method: string,
  path: string,
  body?: unknown
): Promise<any> {
  const opts: RequestInit = { method, credentials: 'include' };
  if (body !== undefined) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    // keepalive-empty or non-JSON body; fall through to status handling
  }
  if (!res.ok) {
    throw new Error(
      data && data.error ? data.error : `${res.status} ${res.statusText}`
    );
  }
  return data;
}
