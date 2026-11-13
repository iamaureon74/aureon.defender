"use strict";

const params = new URLSearchParams(location.search);
const kind = params.get("kind");
const title = document.getElementById("title");
const lines = document.getElementById("lines");
const actions = document.getElementById("actions");
const extra = document.getElementById("extra");
const stateIcon = document.getElementById("state-icon");

// Set threat-level state on body so CSS activates the right color system.
function setThreatState(state, icon) {
  document.body.className = state;
  if (stateIcon && icon) stateIcon.textContent = icon;
}

function paragraph(text) {
  const element = document.createElement("p");
  element.textContent = text;
  lines.append(element);
  return element;
}
function button(label, primary, onClick) {
  const element = document.createElement("button");
  element.textContent = label;
  if (primary) element.className = "primary";
  element.addEventListener("click", onClick);
  actions.append(element);
}
async function closeThisTab() {
  const tab = await Shield.api.tabs.getCurrent();
  if (tab) await Shield.api.tabs.remove(tab.id);
}

async function lookalike() {
  setThreatState("danger", "◈");
  const url = /^https?:\/\//i.test(params.get("url") || "") ? params.get("url") : "";
  const host = Shield.hostOf(url);
  const known = Shield.BRANDS.find((entry) => entry.name === params.get("brand"));
  // Only a brand and a real domain from the shield's own table can be offered; a
  // crafted address to this page cannot point "the real site" anywhere else.
  const brand = known ? known.name : "a known brand";
  const real = known && known.domains.includes(params.get("real")) ? params.get("real") : known ? known.domains[0] : "";
  const reason = (params.get("reason") || "").slice(0, 80);
  title.textContent = `This is not ${brand}.`;
  title.className = "warn";
  paragraph(`${host} looks like ${brand} (${reason}), but ${brand} lives at ${real}. Pages like this exist to take a password or a card number.`);
  const code = document.createElement("code");
  code.textContent = url;
  const where = paragraph("You were going to: ");
  where.append(code);
  if (real) button("Go to the real " + real, true, () => { location.replace("https://" + real); });
  button("Back to safety", false, () => closeThisTab());
  if (url) {
    button("I know this site, continue", false, async () => {
      await Shield.send({ type: "lookalike.allow", site: Shield.siteOf(host) });
      location.replace(url);
    });
  }
}

async function download() {
  setThreatState("caution", "◎");
  const id = parseInt(params.get("id"), 10);
  const info = await Shield.send({ type: "download.info", id });
  title.textContent = "Keep this download?";
  title.className = "warn";
  if (!info || info.error) {
    // A tab restored from an earlier session: nothing to decide, so it closes itself.
    paragraph("Nothing to decide here: this download is no longer waiting. This tab closes by itself.");
    button("Close", true, () => closeThisTab());
    setTimeout(() => closeThisTab().catch(() => {}), 1500);
    return;
  }
  const code = document.createElement("code");
  code.textContent = info.name;
  paragraph("File: ").append(code);
  paragraph("From: " + (info.source || info.url));
  const list = document.createElement("ul");
  for (const reason of info.reasons) {
    const item = document.createElement("li");
    item.textContent = reason;
    list.append(item);
  }
  lines.append(list);
  // What the file really is: the shield's static examination (it is never opened or run).
  const exam = paragraph("Examining the file…");
  const showExam = (scan) => {
    if (!scan) return false;
    exam.replaceChildren();
    if (scan.error) { exam.textContent = "Could not examine the file: " + scan.error; return true; }
    exam.textContent = (scan.knownMalware ? "Known malware. " : "") + "Real type: " + scan.type + ". ";
    const found = document.createElement("ul");
    for (const finding of scan.findings.length ? scan.findings : ["nothing unusual inside"]) { const li = document.createElement("li"); li.textContent = finding; found.append(li); }
    exam.after(found);
    return true;
  };
  if (!showExam(info.scan)) {
    let tries = 0;
    const poll = setInterval(async () => {
      const again = await Shield.send({ type: "download.info", id });
      if (showExam(again && again.scan) || ++tries > 10) { clearInterval(poll); if (tries > 10 && !(again && again.scan)) exam.remove(); }
    }, 1200);
  }
  if (info.virusTotal) {
    if (info.virusTotal.stats) {
      const stats = info.virusTotal.stats;
      paragraph(`VirusTotal: ${stats.malicious || 0} engines call the address malicious, ${stats.suspicious || 0} suspicious, ${stats.harmless || 0} harmless.`);
    } else if (info.virusTotal.pending) {
      paragraph("VirusTotal is still analysing the address.");
    } else if (info.virusTotal.error) {
      paragraph("VirusTotal check failed: " + info.virusTotal.error);
    }
  } else {
    extra.textContent = "Add a VirusTotal key in the shield's settings and downloads like this are checked against its engines too.";
  }
  const decide = async (keep) => {
    const answer = await Shield.send({ type: "download.decide", id, keep });
    if (answer && answer.next) location.replace("warn.html?kind=download&id=" + answer.next);
    else closeThisTab();
  };
  button("Delete it", true, () => decide(false));
  button("Keep it, I asked for this file", false, () => decide(true));
}

function focus() {
  setThreatState("info", "◈");
  const site = params.get("site") || "this site";
  title.textContent = "Focus hours.";
  paragraph(`${site} is on your focus list, and it is inside the hours you set. It will open again when they end.`);
  button("Back", true, () => history.length > 1 ? history.back() : closeThisTab());
  button("Change focus hours", false, () => Shield.api.runtime.openOptionsPage());
}

function parental() {
  setThreatState("locked", "◆");
  title.textContent = "Not on this browser.";
  paragraph("Parental mode is on, and this address is on the blocked list or matched an adult keyword. A parent can turn the mode off in the shield's settings with the PIN.");
  button("Back", true, () => history.length > 1 ? history.back() : closeThisTab());
}

function plainHttp() {
  setThreatState("caution", "◎");
  const url = /^http:\/\//i.test(params.get("url") || "") ? params.get("url") : "";
  const host = Shield.hostOf(url);
  title.textContent = "This site has no secure version.";
  title.className = "warn";
  paragraph(`${host || "This site"} only works over plain http. On this network, whoever runs the wifi can read the page and anything you type into it.`);
  paragraph("Fine for reading. Do not sign in or enter card numbers here unless your vpn is on.");
  button("Go back", true, () => history.length > 2 ? history.go(-2) : closeThisTab());
  if (url) {
    button("Open it anyway (reading only)", false, async () => {
      await Shield.send({ type: "network.allowHttp", url });
      location.replace(url);
    });
  }
}

if (kind === "lookalike") lookalike();
else if (kind === "http") plainHttp();
else if (kind === "download") download();
else if (kind === "focus") focus();
else if (kind === "parental") parental();
else {
  title.textContent = "Nothing to show.";
  button("Close", true, () => closeThisTab());
}
