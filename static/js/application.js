
// A $( document ).ready() block.
$( document ).ready(function() {
  
  function getClients() {
    // Use ajax to get the clients real quick
    $.getJSON("/getclients", function(resp) {
      for (const [key, value] of Object.entries(resp)) {
        console.log(`${key}: ${value}`);
        var row = $('<tr/>');
        row.append($('<td/>').html(key));
        row.append($('<td/>').html(value.hostname));
        $("#clients").append(row);
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
    row.append($('<td/>').html(key));
    row.append($('<td/>').html(value.hostname));
    $("#clients").append(row);
  });

  getClients();
  
});

