// Clean URLs for the site: a CloudFront Function that runs on each request for a page,
// before CloudFront fetches it from S3. The pages are files like rsvp.html in S3, but
// their addresses have no ".html":
//
//   /rsvp          serves rsvp.html (the address bar keeps /rsvp)
//   /rsvp.html     redirects to /rsvp, keeping any ?query
//   /index.html    redirects to /
//   /rsvp/         redirects to /rsvp
//
// "/" itself is CloudFront's default root object (the home_page variable).
// backend/scripts/dev_server.py follows the same rules locally.

function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.length > 1 && uri.slice(-1) === "/") {
    return redirect(uri.slice(0, -1), request.querystring);
  }

  if (uri.slice(-5) === ".html") {
    var page = uri.slice(0, -5);
    return redirect(page === "/index" ? "/" : page, request.querystring);
  }

  // A path whose last part has no "." is a page; files like /css/style.css have one.
  var name = uri.slice(uri.lastIndexOf("/") + 1);
  if (name !== "" && name.indexOf(".") === -1) {
    request.uri = uri + ".html";
  }
  return request;
}

function redirect(location, querystring) {
  return {
    statusCode: 301,
    statusDescription: "Moved Permanently",
    headers: { location: { value: location + query(querystring) } },
  };
}

// CloudFront gives the query string as { name: { value, multiValue } }.
function query(querystring) {
  var parts = [];
  for (var name in querystring) {
    var param = querystring[name];
    var values = param.multiValue || [param];
    for (var i = 0; i < values.length; i++) {
      parts.push(name + "=" + values[i].value);
    }
  }
  return parts.length ? "?" + parts.join("&") : "";
}
