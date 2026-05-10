import streamlit as st
import streamlit.components.v1 as components

def render_floating_clock():
    # We use a component to inject JavaScript into the parent window
    js_code = """
    <script>
    (function() {
        var parentDoc = window.parent.document;
        // Check if our clock container already exists to avoid duplicates
        var existingClock = parentDoc.getElementById("floating-clock-container");
        if (existingClock) {
            existingClock.remove(); // Remove old one to apply new styles
        }

        // Create the container
        var clockDiv = parentDoc.createElement("div");
        clockDiv.id = "floating-clock-container";
        clockDiv.style.position = "fixed";
        clockDiv.style.top = "12px"; // align with streamlit header elements
        clockDiv.style.right = "220px"; // move further left to avoid the "Stop" / running indicator
        clockDiv.style.zIndex = "999999";
        clockDiv.style.padding = "4px 8px";
        clockDiv.style.background = "transparent"; // remove bulky background
        clockDiv.style.border = "none";
        clockDiv.style.color = "#94a3b8"; // subtle gray-blue to match dark mode UI
        clockDiv.style.fontSize = "0.85rem";
        clockDiv.style.fontWeight = "500";
        clockDiv.style.letterSpacing = "0.02em";
        clockDiv.style.fontFamily = "'Inter', sans-serif";
        clockDiv.style.display = "flex";
        clockDiv.style.flexDirection = "row"; // single line
        clockDiv.style.alignItems = "center";
        clockDiv.style.gap = "8px"; // space between date and time
        clockDiv.style.pointerEvents = "none"; 

        var dateSpan = parentDoc.createElement("span");
        var timeSpan = parentDoc.createElement("span");
        timeSpan.style.color = "#cbd5e1"; // slightly brighter time
        timeSpan.style.fontWeight = "600";

        clockDiv.appendChild(dateSpan);
        clockDiv.appendChild(timeSpan);
        parentDoc.body.appendChild(clockDiv);

        function updateClock() {
            var now = new Date();
            // Format Date: e.g., "Mon, May 10, 2026"
            var dateOpts = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
            dateSpan.textContent = now.toLocaleDateString('en-US', dateOpts) + " •";
            
            // Format Time: e.g., "06:42:24 PM"
            var timeOpts = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true };
            timeSpan.textContent = now.toLocaleTimeString('en-US', timeOpts);
        }

        updateClock();
        setInterval(updateClock, 1000);
    })();
    </script>
    """
    components.html(js_code, height=0, width=0)
