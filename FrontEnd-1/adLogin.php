<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login Page</title>
    <link rel="stylesheet" href="login.css">
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="adLogin.css">
    
    
</head>
<body>

<?php

if(isset($_POST["login"])){
    $email=$_POST["email"];
    $password=$_POST["password"];

    require_once "database.php";

    $sql="SELECT * FROM signup WHERE email='$email'";
    $result=mysqli_query($conn, $sql);
    $result2=mysqli_fetch_array($result, MYSQLI_ASSOC);
    if($result2["usertype"]=="admin"){
        if(password_verify($password, $result2["password"])){
            header("Location: ");
            die();
        }
        else{
            echo "<div class='form'>Password does not match</div>";
        }

    }
    else{
        echo "<div class='form'>Admin is not registered</div>";
    }
}

?>

    <div class="main">
        <div class="navbar">
            <div class="icon">
                
                <h2 class="logo">FoundIT</h2>
            </div>
            
            <div class="menu">
                <ul>
                    <li><a href="index.html">HOME</a></li>
                    <li><a href="About.html">ABOUT</a></li>
                    <li><a href="contact.html">CONTACT</a></li>
                    <!-- <li><a href="pricing.html">PRICING</a></li> -->
                    <li><a href="signup.php">SIGNUP</a></li>
                </ul>
            </div>
            <div class="login">
                
                <a href="login.php"> <button class="btn">USER LOGIN</button></a>
            </div>
            <div class="AdminLogin">
                <a href="adLogin.php"> <button class="adbtn">ADMIN LOGIN</button></a>
            </div>
            
            <form action="interface2.html">
                
            
            <div class="form">
                <h2>Admin Login </h2>
                <input type="email" id="email" name="email" placeholder="Email">
                <input type="password" id="password" name="password" placeholder="Password">
                <a href="interface2.html"></a><button class="btnn" onclick="return validation()" type="submit" name="login">Login</button></a>

                <p class="link">Don't have an account?<br>
                <a href="signup.php">Sign up </a> here</a></p>
            </div>
        </form>
      </div>
    </div>
    <script src="login.js"></script>     
</body>
</html>