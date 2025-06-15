#!/usr/bin/env -S awk -f
#
# This is an awk script to filter the ERD generated from eralchemy.
# https://github.com/eralchemy/eralchemy
#
# The output from eralchemy when selecting markdown format with mermaid
# sub-format (see Makefile:gen-erd) seems to be the mermaid format inside HTML
# comments, followed by a link to https://mermaid.ink to make it easy to
# generate an image from the mermaid data.
#
# # This does not work too well, since it seems we have some issues with the
# relationship details generated, which makes the mermaid data invalid.
#
# For example, these are relationships that are generate:
#
# battery None--0+ bat_cap_history : has
# battery None--None battery_image : has
#
# The `None` is invalid (see
# https://mermaid.js.org/syntax/entityRelationshipDiagram.html#relationship-syntax)
# and should really be a one-to-zero and zero-or-one cardinalities respectively.
#
# This script extracts the mermaid data between the HTML comments, and fixes
# the relationships

# Wait for the start of comment
/<!--/ {
    # Set the extract flag
    extract=1
    # Print a markdown level one header and the start of the mermaid syntax
    # marker
    print "# Battery Capacity Meter ERD\n\n```mermaid"
    # Skip this line
    next
}

# When we see the end of comment line, close the mermaid syntax and exit
/-->/ {
    print "```"
    exit
}

# Test the extract flag. If set, we are extracting the lines
extract {
    # Fix the None-- and --None relationship cardinalities and print the line
    gsub(/None--/, "one or zero--")
    gsub(/--None/, "--zero or one")
    print
}
