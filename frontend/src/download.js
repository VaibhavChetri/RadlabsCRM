// download.js
// -----------
// Save a file the API sent (axios response with responseType: 'blob').
// The file name comes from the Content-Disposition header when there is one.

export function saveDownload(res, fallbackName) {
  const disposition = res.headers['content-disposition'] || '';
  const fileName = /filename="([^"]+)"/.exec(disposition)?.[1] || fallbackName;
  const url = URL.createObjectURL(res.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}
