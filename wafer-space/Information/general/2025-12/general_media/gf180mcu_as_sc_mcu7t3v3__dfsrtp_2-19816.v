module gf180mcu_as_sc_mcu7t3v3__dfsrtp_2(
	input VPW,
	input VNW,
	input VDD,
	input VSS,

	input CLK,
	input D,
	input RN,
	input SN,
	output Q
);

reg state;
wire sr;

assign sr = ~(RN & SN);

always @(posedge CLK or posedge sr) begin
    if (sr == 1'b1) begin
	if (RN == 1'b0) begin
	    Q <= 1'b0;
	end else if (SN == 1'b0) begin
	    Q <= 1'b1;
	end
    end else begin
	Q <= state;
    end
end

endmodule
