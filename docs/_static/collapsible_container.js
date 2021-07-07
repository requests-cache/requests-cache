// Taken from: https://github.com/plone/training/blob/master/_templates/page.html

$(document).ready(function() {
    $(".toggle > *").hide();
    $(".toggle .admonition-title").show();
    $(".toggle .admonition-title").click(function() {
        $(this).parent().children().not(".admonition-title").toggle(400);
        $(this).parent().children(".admonition-title").toggleClass("open");
    })
});

