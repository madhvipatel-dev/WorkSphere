document.addEventListener("DOMContentLoaded", function () {

    const sidebar = document.getElementById("sidebar");
    const menuButton = document.getElementById("mobileMenuButton");
    const overlay = document.getElementById("sidebarOverlay");

    function openSidebar() {
        if (!sidebar || !overlay) {
            return;
        }

        sidebar.classList.add("mobile-open");
        overlay.classList.add("show");
        document.body.style.overflow = "hidden";
    }

    function closeSidebar() {
        if (!sidebar || !overlay) {
            return;
        }

        sidebar.classList.remove("mobile-open");
        overlay.classList.remove("show");
        document.body.style.overflow = "";
    }

    if (menuButton) {
        menuButton.addEventListener("click", function () {

            if (sidebar.classList.contains("mobile-open")) {
                closeSidebar();
            } else {
                openSidebar();
            }

        });
    }

    if (overlay) {
        overlay.addEventListener("click", closeSidebar);
    }


    /*
     * Close the mobile sidebar after selecting a page.
     */
    if (sidebar) {

        const navigationLinks =
            sidebar.querySelectorAll("a.nav-item");

        navigationLinks.forEach(function (link) {

            link.addEventListener("click", function () {

                if (window.innerWidth <= 900) {
                    closeSidebar();
                }

            });

        });

    }


    /*
     * Return to normal desktop state when
     * the browser becomes wider again.
     */
    window.addEventListener("resize", function () {

        if (window.innerWidth > 900) {
            closeSidebar();
        }

    });

});