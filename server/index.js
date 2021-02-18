const bodyParser = require('body-parser');
const config = require('config');
const express = require('express');
const helmet = require('helmet');
const http = require('http');
const mysql = require('mysql');
const path = require('path');
const rateLimit = require('express-rate-limit');

const dbAuth = config.get('dbAuth');

const app = express();

var listener = app.listen(8000, function() {
  console.log('Listening on port ' + listener.address().port); //Listening on port 8000, which is being redirected to port 80
});


const limiter = rateLimit({
  windowMS: 0, // 0 ms
  max: Infinity // Limit each IP tp Infinity requests every windowMS
});

app.use(bodyParser.urlencoded({
  extended: true
}));
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, './public'))); // Actually serves the website
app.use(helmet()); // Secure headers for node.js
app.use(limiter); // RateLimit

let db = mysql.createConnection(dbAuth);

function getUserData(username) {
  return new Promise((resolve, reject) => {
    let query;
    if (username == 'all') {
      query = 'SELECT * FROM nicecount ORDER BY value ASC';
    } else {
      query = 'SELECT * FROM nicecount WHERE username = ? ORDER BY value DESC';
    }
    db.query(query, [username], (err, rows) => {
      // The addition of the username bit was not part of the solution, it's just part of my project.
      if (rows == undefined) {
        reject(new Error('Error: rows is undefined.'));
      } else {
        resolve(rows);
      }
    });
  });
}
// To add a new reddit account:
app.post('/insert', (req, res) => { // a POST request on /add
  console.log('Recieved INSERT');
  console.log(req.body);
  res.json({
    response: 'This feature has not yet been implemented. Sorry!'
  });
  // db.serialize(() => { // Forces SQLite to execute one statement at a time
  //   db.run('INSERT INTO nicecount(username,value) VALUES(?,?)', [req.body.username, req.body.value], (err) => {
  //     if (err) {
  //       return console.log(err.message);
  //     }
  //     console.log('New account has been added');
  //     res.json({
  //       response: `Account u/${req.body.username} has been inserted onto the database with ${req.body.value} karma`
  //     });
  //   });
  // });
});

// To query the database
app.post('/query', (req, res) => {
  console.log('Recieved QUERY');
  console.log(req.body);

  // Get data from sqlite3 database
  // row = getUserData(req.body.username);

  getUserData(req.body.username)
    .then(response => {
      data = [];
      for (let row of response) {
        data.push({
          username: row.username,
          value: row.value
        });
      }
      if (data == []) {
        res.json({
          length: 0,
          data: null
        });
      } else {
        res.json({
          length: data.length,
          data: data
        });
      }
    })
    .catch(err => {
      console.log('Error: ' + err);
    });


});