function changeColorOnHold(linkId) {
    var link = document.getElementById(linkId);

    function addBlack() {
        link.classList.add('text-black');
    }

    function addWarning() {
        link.classList.remove('text-black');
        link.classList.add('text-warning');
    }

    link.addEventListener('mousedown', addBlack);
    link.addEventListener('mouseup', addWarning);
    link.addEventListener('mouseleave', addWarning);

    link.addEventListener('touchstart', addBlack);
    link.addEventListener('touchend', addWarning);
}

changeColorOnHold('changeColor');