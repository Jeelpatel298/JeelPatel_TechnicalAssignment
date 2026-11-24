import { api, busy } from './client.js';

const form = document.querySelector('#login-form');
const notice = document.querySelector('#login-error');

form.addEventListener('submit', event => {
  event.preventDefault();
  notice.hidden = true;
  busy(event.submitter, async () => {
    await api('/login', 'POST', Object.fromEntries(new FormData(form)));
    location.assign('/');
  }, error => {
    notice.textContent = error.message;
    notice.hidden = false;
  });
});
