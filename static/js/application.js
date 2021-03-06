
// A $( document ).ready() block.
$( document ).ready(function() {

  function getClients() {
    // Use ajax to get the clients real quick
    $.getJSON("/getclients", function(resp) {
      for (const [key, value] of Object.entries(resp)) {
        console.log(`${key}: ${value}`);
        var row = $('<tr/>');
        row.append($('<td/>').html(key.substring(0, 8)));
        row.append($('<td/>').html(value.hostname));
        row.attr('id', key);
        $("#clients").append(row);

      }
      
    });
  }

  function getServers() {
    // Use ajax to get the clients real quick
    $.getJSON("/getservers", function(resp) {
      for (const [key, value] of Object.entries(resp)) {
        console.log(`${key}: ${value}`);
        var row = $('<tr/>');
        row.append($('<td/>').html(key.substring(0, 8)));
        row.append($('<td/>').html(value.hostname));
        row.attr('id', key);
        $("#servers").append(row);

      }
      
    });
  }

  $("#ping-button").click(function(event){
    event.preventDefault();
    $.post("/send-command").done(function(data) {
      console.log("Successful in the POST to send-command");
    })
  });

  const socket = io();
  socket.on('connect', () => {
    console.log("Connected to server with socket.io");
  });

  socket.on('new worker', (node_details) => {
    console.log("New worker node")
    var row = $('<tr/>');
    row.append($('<td/>').html(node_details.client_id.substring(0, 8)));
    row.append($('<td/>').html(node_details.hostname));
    row.attr('id', node_details.client_id);
    row.hide();
    $("#clients").append(row);
    row.slideDown('slow');
  });

  socket.on('worker left', (client_id) => {
    // Remove the row from the table
    console.log("Worker node left: " + client_id);
    $("#" + client_id).remove();
  });

  socket.on('new server', (node_details) => {
    console.log("New server node")
    var row = $('<tr/>');
    row.append($('<td/>').html(node_details.client_id.substring(0, 8)));
    row.append($('<td/>').html(node_details.hostname));
    row.attr('id', node_details.client_id);
    row.hide();
    $("#servers").append(row);
    row.slideDown('slow');
  });

  socket.on('server left', (client_id) => {
    // Remove the row from the table
    console.log("Server node left: " + client_id);
    $("#" + client_id).remove();
  });



  getClients();
  getServers();
  
});

