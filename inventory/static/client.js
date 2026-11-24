export async function api(path, method = 'GET', data) {
  const headers = {};
  if (method !== 'GET') {
    headers['X-CSRF-Token'] = document.querySelector('meta[name="csrf-token"]').content;
  }
  let body = data;
  if (data !== undefined && !(data instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(data);
  }
  const response = await fetch('/api' + path, { method, headers, body });
  if (response.status === 204) return null;
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(result.error || 'The request could not be completed.');
    error.rows = result.errors;
    throw error;
  }
  return result;
}

export async function busy(button, task, onError) {
  button.disabled = true;
  try {
    await task();
  } catch (error) {
    onError(error);
  } finally {
    button.disabled = false;
  }
}
