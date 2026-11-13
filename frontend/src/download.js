// download.js
// -----------
// Save a file the API sent (axios response with responseType: 'blob').
// The file name: `overrideName` if given, else the Content-Disposition header, else the fallback.

export function saveDownload(res, fallbackName, overrideName) {
  const disposition = res.headers['content-disposition'] || '';
  const fileName = overrideName || /filename="([^"]+)"/.exec(disposition)?.[1] || fallbackName;
  const url = URL.createObjectURL(res.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}
