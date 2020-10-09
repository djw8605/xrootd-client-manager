
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

  getClients();
  
});

