function serialize(data) {
  let obj = {};
  for (let [key, value] of data) {
    obj[key] = value;
  }
  return obj;
}

document.addEventListener('submit', e => {

  // Store reference to form to make later code easier to read
  const form = e.target;

  // Get all field data from the form
  let data = new FormData(form);

  // Convert to an object
  let formObj = serialize(data);

  // Post data using the Fetch API
  fetch(form.action, {
      headers: {
        "Content-type": "application/json"
      },
      method: form.method,
      body: JSON.stringify(formObj)
    })
    .then(function(res) {
      return res.json();
    })
    .then(data => {
      // alert(JSON.stringify(data));
      // Create result message container and copy HTML from doc
      let result = document.createElement('p');
      result.innerHTML = JSON.stringify(data);

      // And replace the form with the response children
      document.getElementById('serverResponse').replaceChild(result, document.getElementById('serverResponse').childNodes[1]);

    });

  // Prevent the default form submit
  e.preventDefault();

});