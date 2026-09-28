-- File for independent utility functions used by multiple files
-- Currently only has a string splitter functions
local Utilities = {}

-- inspired by https://stackoverflow.com/questions/40149617/split-string-with-specified-delimiter-in-lua
-- Splits the given string using commas as delimiters, converts them to numbers,
-- then returns the split strings as a table.
function Utilities.Split_Numbers(str)
    local output = {}
    for substr in str:gmatch("([^,]+)") do
        table.insert(output, tonumber(substr))
    end
    return output
end

-- inspired by https://stackoverflow.com/questions/40149617/split-string-with-specified-delimiter-in-lua
-- Splits the given string using commas as delimiters,
-- then returns the split strings as a table.
function Utilities.Split_Words(str)
    local output = {}
    for substr in str:gmatch("([^,]+)") do
        table.insert(output, substr)
    end
    return output
end

return Utilities