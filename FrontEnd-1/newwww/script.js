const Switches = document.getElementById('Switches');
const Routers = document.getElementById('Routers');
const switchessection = document.getElementById('switches-section');
const routerssection = document.getElementById('routers-section');
const apisettingssection = document.getElementById('api-settings-section');
const apiSetting = document.getElementById('apiSetting');


function dashboardLogic() {
    Switches.addEventListener("click", () => {
        switchessection.style.display = "block";
        routerssection.style.display = "none";
        apisettingssection.style.display = "none";
    });

    Routers.addEventListener("click", () => {
        switchessection.style.display = "none";
        routerssection.style.display = "block";
        apisettingssection.style.display = "none";
    });

    apiSetting.addEventListener("click", () => {
        switchessection.style.display = "none";
        routerssection.style.display = "none";
        apisettingssection.style.display = "block";
    });
}

dashboardLogic();