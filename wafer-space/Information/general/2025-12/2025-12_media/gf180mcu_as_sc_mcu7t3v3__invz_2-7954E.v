module gf180mcu_as_sc_mcu7t3v3__invz_2(
        input VPW,
        input VNW,
        input VDD,
        input VSS,

        input A,
        input EN,
        output Y
);

assign Y = (EN == 1'b1) ? ~A : 1'bz;

endmodule

