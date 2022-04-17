function ShowPassword(id) {
    var test_input = document.getElementById(id);
    test_input.type = test_input.type == "text" ? "password" : "text";
}
