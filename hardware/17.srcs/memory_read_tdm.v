`timescale 1ns / 1ps
/////////////////////////////////////////////////
// OSC1 - LITE
// Version 1.0.0
// Yoon's Lab - U of M
/////////////////////////////////////////////////

// Time Division Multiplexer for memory read
// Collects read request from 12 channels, and update the result in no more than 24 clock cycles

module memory_read_tdm(
    input wire clk,
    
    output wire [15:0] mem_addr,
    input wire [17:0] mem_data,
    
	input wire [203:0] req_addr,
	output reg[107:0] req_data
);
    reg [4:0] counter;
    
    assign mem_addr = req_addr[(counter[4:1]*17+1) +: 16];
    
    always @(negedge clk) begin
        if (counter >= 23) begin
            counter <= 0;
        end else begin
            counter <= counter  + 1;
        end
        if (counter[0]) begin
            req_data[counter[4:1] * 9 +: 9] <= req_addr[counter[4:1]*17] ? mem_data[17:9] : mem_data[8:0];
        end
    end
endmodule