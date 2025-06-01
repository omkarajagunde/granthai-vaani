import requests


def get_health_packages():
    url = "https://api.yodadiagnostics.com/tests/popular/health-packages"
    response = requests.get(url)
    response = response.json()

    packages = []
    for pkg in response["data"]:
        pkg.pop("locations", None)
        packages.append(pkg)
    return packages


def get_test_details():
    url = "https://api.yodadiagnostics.com/tests/paginate/individual/724/1"
    response = requests.get(url)
    response = response.json()

    tests = []
    for test in response["data"]["docs"]:
        test.pop("locations", None)
        tests.append(test)
    return tests


def book_appointment(**kwargs):
    print("BOOK APPOINTMENT: ", kwargs)
    return "Booking successful"


function_map = {
    "yoda_diagnostics": {
        "get_health_packages": get_health_packages,
        "get_test_details": get_test_details,
        "book_appointment": book_appointment,
    }
}


def get_tool(assistant_name, tool_name):
    return function_map[assistant_name][tool_name]
