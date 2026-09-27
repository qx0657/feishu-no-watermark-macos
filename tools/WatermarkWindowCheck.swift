import ApplicationServices
import Foundation

guard CommandLine.arguments.count == 2, let pid = pid_t(CommandLine.arguments[1]) else {
    fputs("usage: WatermarkWindowCheck <pid>\n", stderr)
    exit(2)
}

let app = AXUIElementCreateApplication(pid)
var value: CFTypeRef?
let error = AXUIElementCopyAttributeValue(app, kAXWindowsAttribute as CFString, &value)
guard error == .success, let windows = value as? [AXUIElement] else {
    fputs("cannot read accessibility windows (grant Accessibility permission to the terminal)\n", stderr)
    exit(3)
}

var found = false
for window in windows {
    var titleValue: CFTypeRef?
    AXUIElementCopyAttributeValue(window, kAXTitleAttribute as CFString, &titleValue)
    let title = titleValue as? String ?? ""
    if title.localizedCaseInsensitiveContains("watermark") {
        print("watermark window found: \(title)")
        found = true
    }
}

if found {
    exit(1)
}
print("no accessibility window title contains 'watermark'")
