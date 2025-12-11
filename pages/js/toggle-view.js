// Implements the toggle-view and query-checkbox utility classes.
// toggle-view: A simple show/hide toggle box; uses 
// query-checkbox: A checkbox whose id updates the frame search
import {frameSearch, setFrameSearch, framePage, openLocalPage} from './frame.js';

function setVisible(element,newVisible,changeURL) {
    // Set the visibility of this toggle-view element
    // element: the html element corresponding to the toggle button
    // newVisible: true = show, false = hide, null = no change, any other value = toggle
    // if changeURL, then update the URL hash query component

    if (newVisible === null)
        return;

    let body = document.getElementById(element.id + ".b");
    let isVisible = window.getComputedStyle(body).display !== "none";

    if (newVisible === isVisible)
        return;

    if (!isVisible) {
        body.style.display = "";
        for (let n = 1; n <= 4; n++) {
            body.classList.remove(`hide-thin-screen-${n}`); // Remove width-conditional hiding classes
        }
        body.classList.remove("javascript-hide");
        if (element.classList.contains("hide-self")) // Hide ourselves when showing the body
            element.style.display = "none";
        else
            element.className = "fa fa-minus-square toggle-view";
    } else {
        body.style.display = "none";
        element.className = "fa fa-plus-square toggle-view";
    }

    if (changeURL) {
        let params = frameSearch();
        let toggled = (params.get("toggle") || "").split(".");
        if (toggled[0] === "")
            toggled.splice(0,1);
        let index = toggled.indexOf(element.id);
        if (index === -1) {
            toggled.push(element.id);
        } else {
            toggled.splice(index,1);
        }
        params.set("toggle",toggled.join("."));
        setFrameSearch(params);
    }
}

function toggleClickListener(event) {
    event.preventDefault();
    setVisible(this,"toggle",true);
}

function checkboxClickListener(event) {
    let params = frameSearch();
    if (this.checked)
        params.set(this.id,"")
    else
        params.delete(this.id);
    params.delete("xPage"); // Go back to the first search page - only relevant on search pages
    openLocalPage(framePage(),String(params),"keep_scroll");
}

export function loadToggleView(frame) {
    if (!frame)
        frame = document;

    let params = frameSearch()
    let initView = params.has("showAll") ? true : (params.has("hideAll") ? false : null)
    let toggled = (params.get("toggle") || "").split(".");
    if (toggled[0] === "")
        toggled.splice(0,1);

    let togglers = frame.getElementsByClassName("toggle-view");
    for (let t of togglers) {
        if (toggled.indexOf(t.id) === -1)
            setVisible(t,initView);
        else if (initView === null)
            setVisible(t,"toggle");
        else
            setVisible(t,!initView);
        t.addEventListener("click", toggleClickListener);
    }

    let checkboxes = frame.getElementsByClassName("query-checkbox");
    for (let c of checkboxes) {
        c.checked = params.has(c.id);
        c.addEventListener("click",checkboxClickListener)
    }
}