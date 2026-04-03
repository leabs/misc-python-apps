from __future__ import annotations

from dataclasses import dataclass
import json
from subprocess import CompletedProcess, run
import time


JS_HELPERS = r"""
const normalize = (value) => String(value ?? "").replace(/\s+/g, " ").trim().toLowerCase();

const isVisible = (element) => {
  if (!element) return false;
  const style = window.getComputedStyle(element);
  if (style.display === "none" || style.visibility === "hidden") return false;
  return Boolean(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
};

const getRect = (element) => element.getBoundingClientRect();

const getTextControls = (container) =>
  Array.from(container.querySelectorAll('input:not([type="hidden"]), textarea, [contenteditable="true"]'))
    .filter(isVisible);

const getComboControls = (container) =>
  Array.from(
    container.querySelectorAll(
      '[role="combobox"], input[role="combobox"], button[aria-haspopup="listbox"], select'
    )
  ).filter(isVisible);

const labelMatchScore = (textValue, wanted) => {
  const text = normalize(textValue);
  const wantedText = normalize(wanted);
  if (!text || !wantedText) return Number.POSITIVE_INFINITY;
  if (text === wantedText) return 0;
  if (text.startsWith(`${wantedText} `) || text.startsWith(`${wantedText}*`) || text.startsWith(`${wantedText}:`)) {
    return 1;
  }
  if (text.includes(wantedText)) return 2;
  return Number.POSITIVE_INFINITY;
};

const matchingTextNodes = (container, wanted) =>
  Array.from(container.querySelectorAll("label, span, div, p, h2, h3, h4, legend"))
    .filter((element) => isVisible(element))
    .map((element) => ({
      element,
      score: labelMatchScore(element.textContent, wanted),
      rect: getRect(element),
    }))
    .filter((entry) => Number.isFinite(entry.score))
    .sort((left, right) => {
      if (left.score !== right.score) return left.score - right.score;
      const leftArea = left.rect.width * left.rect.height;
      const rightArea = right.rect.width * right.rect.height;
      return leftArea - rightArea;
    })
    .map((entry) => entry.element);

const pickEntryContainer = () => {
  const titleLabels = matchingTextNodes(document, "title");
  const matches = new Set();
  for (const titleLabel of titleLabels) {
    let current = titleLabel;
    for (let depth = 0; depth < 8 && current; depth += 1) {
      const text = normalize(current.innerText);
      if (
        text.includes("title") &&
        text.includes("description") &&
        text.includes("definition") &&
        text.includes("active") &&
        (getTextControls(current).length + getComboControls(current).length) >= 4
      ) {
        matches.add(current);
      }
      current = current.parentElement;
    }
  }

  return Array.from(matches)
    .sort((left, right) => {
      const leftRect = getRect(left);
      const rightRect = getRect(right);
      if (Math.abs(leftRect.top - rightRect.top) > 4) {
        return rightRect.top - leftRect.top;
      }
      const leftArea = leftRect.width * leftRect.height;
      const rightArea = rightRect.width * rightRect.height;
      return leftArea - rightArea;
    })
    .at(0) ?? null;
};

const findControl = (container, label, kind) => {
  const labelNode = matchingTextNodes(container, label).at(0) ?? null;
  const controls = kind === "combo" ? getComboControls(container) : getTextControls(container);
  if (!controls.length) return null;

  if (labelNode?.tagName === "LABEL" && labelNode.htmlFor) {
    const direct = document.getElementById(labelNode.htmlFor) ?? container.querySelector(`#${CSS.escape(labelNode.htmlFor)}`);
    if (direct && isVisible(direct)) return direct;
  }

  if (labelNode) {
    const labelRect = getRect(labelNode);
    let bestControl = null;
    let bestScore = Number.POSITIVE_INFINITY;
    for (const control of controls) {
      const controlRect = getRect(control);
      const verticalPenalty = controlRect.top + 8 < labelRect.bottom ? 1000 : 0;
      const distance = Math.abs(controlRect.top - labelRect.bottom) * 10 + Math.abs(controlRect.left - labelRect.left);
      const score = verticalPenalty + distance;
      if (score < bestScore) {
        bestControl = control;
        bestScore = score;
      }
    }
    if (bestControl) return bestControl;
  }

  const fallbackOrder = { title: 0, description: 1, definition: 2, source: 3 };
  const ordered = controls.sort((left, right) => {
    const leftRect = getRect(left);
    const rightRect = getRect(right);
    if (Math.abs(leftRect.top - rightRect.top) > 4) {
      return leftRect.top - rightRect.top;
    }
    return leftRect.left - rightRect.left;
  });
  return ordered[fallbackOrder[normalize(label)] ?? 0] ?? null;
};

const sortControlsByPosition = (controls) =>
  Array.from(controls).sort((left, right) => {
    const leftRect = getRect(left);
    const rightRect = getRect(right);
    if (Math.abs(leftRect.top - rightRect.top) > 8) {
      return leftRect.top - rightRect.top;
    }
    return leftRect.left - rightRect.left;
  });

const getOrderedTextControls = (container) => sortControlsByPosition(getTextControls(container));

const getOrderedComboControls = (container) => sortControlsByPosition(getComboControls(container));

const setTextValue = (element, value) => {
  element.scrollIntoView({ block: "center", inline: "nearest" });
  element.focus();

  if (element.isContentEditable) {
    document.execCommand("selectAll", false);
    document.execCommand("insertText", false, value);
    return;
  }

  const descriptorSource = element.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(descriptorSource, "value")?.set;
  if (setter) {
    setter.call(element, value);
  } else {
    element.value = value;
  }

  try {
    element.dispatchEvent(new InputEvent("input", { bubbles: true, data: value, inputType: "insertText" }));
  } catch (_error) {
    element.dispatchEvent(new Event("input", { bubbles: true }));
  }
  element.dispatchEvent(new Event("change", { bubbles: true }));
  element.dispatchEvent(new Event("blur", { bubbles: true }));
};

const dispatchKey = (element, key) => {
  const eventInit = { bubbles: true, cancelable: true, key };
  element.dispatchEvent(new KeyboardEvent("keydown", eventInit));
  element.dispatchEvent(new KeyboardEvent("keypress", eventInit));
  element.dispatchEvent(new KeyboardEvent("keyup", eventInit));
};

const findOption = (comboRect, optionText) => {
  const candidates = Array.from(document.querySelectorAll('[role="option"], li, button, div, span'))
    .filter((element) => isVisible(element) && labelMatchScore(element.textContent, optionText) <= 2);
  return candidates
    .sort((left, right) => {
      const leftRect = getRect(left);
      const rightRect = getRect(right);
      const leftScore = Math.abs(leftRect.top - comboRect.bottom) * 10 + Math.abs(leftRect.left - comboRect.left);
      const rightScore = Math.abs(rightRect.top - comboRect.bottom) * 10 + Math.abs(rightRect.left - comboRect.left);
      return leftScore - rightScore;
    })
    .at(0) ?? null;
};

const setComboValue = (element, optionText) => {
  if (element.tagName === "SELECT") {
    const option = Array.from(element.options).find((candidate) => normalize(candidate.textContent) === normalize(optionText));
    if (!option) {
      return { ok: false, error: `Option '${optionText}' was not found in the active select.` };
    }
    element.value = option.value;
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true };
  }

  element.scrollIntoView({ block: "center", inline: "nearest" });
  element.focus();
  element.click();

  let option = findOption(getRect(element), optionText);
  if (option) {
    option.scrollIntoView({ block: "nearest", inline: "nearest" });
    option.click();
    return { ok: true };
  }

  const inputLike = element.matches('input, textarea, [role="combobox"]')
    ? element
    : element.querySelector?.('input, textarea, [role="combobox"]') ?? null;

  if (inputLike) {
    try {
      const descriptorSource = inputLike.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(descriptorSource, "value")?.set;
      if (setter) {
        setter.call(inputLike, optionText);
      } else if ("value" in inputLike) {
        inputLike.value = optionText;
      }
      inputLike.dispatchEvent(new Event("input", { bubbles: true }));
      inputLike.dispatchEvent(new Event("change", { bubbles: true }));
    } catch (_error) {
      // Ignore and fall through to keyboard confirmation.
    }

    option = findOption(getRect(element), optionText);
    if (option) {
      option.scrollIntoView({ block: "nearest", inline: "nearest" });
      option.click();
      return { ok: true };
    }

    dispatchKey(inputLike, "ArrowDown");
    dispatchKey(inputLike, "Enter");
    return { ok: true };
  }

  dispatchKey(element, "ArrowDown");
  dispatchKey(element, "Enter");
  option = findOption(getRect(element), optionText);
  if (!option) {
    return { ok: false, error: `Option '${optionText}' was not found after opening the active dropdown.` };
  }

  option.scrollIntoView({ block: "nearest", inline: "nearest" });
  option.click();
  return { ok: true };
};

const findAddEntryButton = (container) => {
  const containerRect = getRect(container);
  const buttons = Array.from(document.querySelectorAll('button, a, [role="button"]'))
    .filter((element) => isVisible(element) && normalize(element.textContent) === "add an entry");
  return buttons
    .sort((left, right) => {
      const leftRect = getRect(left);
      const rightRect = getRect(right);
      const leftPenalty = leftRect.top + 8 < containerRect.bottom ? 1000 : 0;
      const rightPenalty = rightRect.top + 8 < containerRect.bottom ? 1000 : 0;
      const leftScore = leftPenalty + Math.abs(leftRect.top - containerRect.bottom) * 10 + Math.abs(leftRect.left - containerRect.left);
      const rightScore = rightPenalty + Math.abs(rightRect.top - containerRect.bottom) * 10 + Math.abs(rightRect.left - containerRect.left);
      return leftScore - rightScore;
    })
    .at(0) ?? null;
};
"""


@dataclass(frozen=True)
class RowPayload:
    title: str
    description: str
    definition: str
    source: str = ""


class AutomationError(RuntimeError):
    """Raised when a Strapi browser automation step fails."""


class StrapiBridge:
    def __init__(self, browser_name: str):
        self.browser_name = browser_name

    def probe_page(self) -> dict[str, object]:
        script = f"""
(() => {{
  {JS_HELPERS}
  const container = pickEntryContainer();
  const orderedTextControls = container ? getOrderedTextControls(container) : [];
  const orderedComboControls = container ? getOrderedComboControls(container) : [];
  const fields = {{
    title: Boolean(container && findControl(container, "title", "text")),
    description: Boolean(container && findControl(container, "description", "text")),
    definition: Boolean(container && findControl(container, "definition", "text")),
    source: Boolean(container && findControl(container, "source", "text")),
    active: Boolean(container && findControl(container, "active", "combo")),
  }};
  const addButton = Boolean(container && findAddEntryButton(container));
  return JSON.stringify({{
    ok: Boolean(container),
    url: window.location.href,
    foundEntryContainer: Boolean(container),
    fields,
    addButton,
    textControlCount: orderedTextControls.length,
    comboControlCount: orderedComboControls.length,
  }});
}})();
"""
        return self._parse_json_result(self._run_javascript(script))

    def fill_row(self, payload: RowPayload, *, add_after: bool) -> dict[str, object]:
        fill_script = f"""
(() => {{
  {JS_HELPERS}
  const payload = {json.dumps(payload.__dict__, ensure_ascii=False)};
  const container = pickEntryContainer();
  if (!container) {{
    return JSON.stringify({{
      ok: false,
      error: "Could not find the current Strapi entry block. Make sure the Enums section is visible."
    }});
  }}

  const orderedTextControls = getOrderedTextControls(container);
  const orderedComboControls = getOrderedComboControls(container);

  const titleField = findControl(container, "title", "text") ?? orderedTextControls[0] ?? null;
  const descriptionField = findControl(container, "description", "text") ?? orderedTextControls[1] ?? null;
  const definitionField = findControl(container, "definition", "text") ?? orderedTextControls[2] ?? null;
  const sourceField = payload.source
    ? (findControl(container, "source", "text") ?? orderedTextControls[3] ?? null)
    : null;
  const activeField = findControl(container, "active", "combo") ?? orderedComboControls.at(-1) ?? null;

  if (!titleField || !descriptionField || !definitionField || !activeField) {{
    return JSON.stringify({{
      ok: false,
      error: "One or more required Strapi fields could not be found in the current entry block."
    }});
  }}

  setTextValue(titleField, payload.title);
  setTextValue(descriptionField, payload.description);
  setTextValue(definitionField, payload.definition);

  if (payload.source && sourceField) {{
    setTextValue(sourceField, payload.source);
  }}

  if (activeField.tagName === "SELECT") {{
    const activeResult = setComboValue(activeField, "TRUE");
    if (!activeResult.ok) {{
      return JSON.stringify({{
        ok: false,
        error: activeResult.error
      }});
    }}
    return JSON.stringify({{
      ok: true,
      row: payload.title,
      activeHandled: true
    }});
  }}

  activeField.scrollIntoView({{ block: "center", inline: "nearest" }});
  activeField.focus();
  activeField.click();

  return JSON.stringify({{
    ok: true,
    row: payload.title,
    activeHandled: false
  }});
}})();
"""
        result = self._parse_json_result(self._run_javascript(fill_script))

        if not bool(result.get("activeHandled")):
            time.sleep(0.2)
            active_result = self._parse_json_result(
                self._run_javascript(
                    f"""
(() => {{
  {JS_HELPERS}
  const container = pickEntryContainer();
  if (!container) {{
    return JSON.stringify({{
      ok: false,
      error: "Could not find the current Strapi entry block while selecting the active value."
    }});
  }}

  const activeField = findControl(container, "active", "combo") ?? getOrderedComboControls(container).at(-1) ?? null;
  if (!activeField) {{
    return JSON.stringify({{
      ok: false,
      error: "Could not find the active dropdown while selecting TRUE."
    }});
  }}

  const activeResult = setComboValue(activeField, "TRUE");
  if (!activeResult.ok) {{
    return JSON.stringify({{
      ok: false,
      error: activeResult.error
    }});
  }}

  return JSON.stringify({{
    ok: true,
    activeHandled: true
  }});
}})();
"""
                )
            )
            result.update(active_result)

        if add_after:
            time.sleep(0.15)
            add_result = self._parse_json_result(
                self._run_javascript(
                    f"""
(() => {{
  {JS_HELPERS}
  const container = pickEntryContainer();
  if (!container) {{
    return JSON.stringify({{
      ok: false,
      error: "Could not find the current Strapi entry block before clicking 'Add an entry'."
    }});
  }}

  const addButton = findAddEntryButton(container);
  if (!addButton) {{
    return JSON.stringify({{
      ok: false,
      error: "Filled the row, but could not find the 'Add an entry' button."
    }});
  }}
  addButton.scrollIntoView({{ block: "center", inline: "nearest" }});
  addButton.click();

  return JSON.stringify({{
    ok: true,
    addAfter: true
  }});
}})();
"""
                )
            )
            result.update(add_result)

        return result

    def _run_javascript(self, script: str) -> str:
        if '"' in self.browser_name:
            raise AutomationError("Browser name cannot contain double quotes.")

        applescript = [
            "on run argv",
            "set jsCode to item 1 of argv",
            f'tell application "{self.browser_name}"',
            "activate",
            "return execute active tab of front window javascript jsCode",
            "end tell",
            "end run",
        ]
        command = ["osascript"]
        for line in applescript:
            command.extend(["-e", line])
        command.append(script)
        completed = run(command, capture_output=True, text=True, check=False)
        self._raise_for_failure(completed)
        return completed.stdout.strip()

    def _parse_json_result(self, raw_result: str) -> dict[str, object]:
        if not raw_result:
            raise AutomationError("The browser returned an empty result.")
        try:
            result = json.loads(raw_result)
        except json.JSONDecodeError as exc:
            raise AutomationError(f"Unexpected browser response: {raw_result}") from exc
        if isinstance(result, dict) and result.get("ok") is False:
            raise AutomationError(str(result.get("error", "Unknown browser automation error.")))
        return result

    def _raise_for_failure(self, completed: CompletedProcess[str]) -> None:
        if completed.returncode == 0:
            return
        message = completed.stderr.strip() or completed.stdout.strip() or "Unknown osascript failure."
        raise AutomationError(message)
