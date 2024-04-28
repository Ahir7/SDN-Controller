function validation() {

    var email=document.getElementById("email");
    var password=document.getElementById("password");


   if (email.value=="") {
        alert("Please enter the email");
        return false;
    } else if (password.value == "") {
        alert("Enter Password");
        return false;
    }
    else if (password.value.length < 6) {
        alert("Password must be of at least 6 characters");
        return false;
    }
    else{
        true;
    }
}
