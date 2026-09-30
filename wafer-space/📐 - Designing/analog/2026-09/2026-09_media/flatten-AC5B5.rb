source = RBA::Layout::new()
source.read($input)

source.each_top_cell do |c|
	cell = source.cell(c)
	puts cell.name
	cell.flatten(1000, true)
end
puts "Complete"

if $output
	source.write($output)
end
