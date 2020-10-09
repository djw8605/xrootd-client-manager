
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

  getClients();
  
});

