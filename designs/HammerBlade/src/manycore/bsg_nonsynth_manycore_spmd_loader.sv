/**
 *  bsg_nonsynth_manycore_spmd_loader.v
 *
 */

`include "bsg_manycore_defines.svh"

module bsg_nonsynth_manycore_spmd_loader
  import bsg_manycore_pkg::*;
  #(parameter `BSG_INV_PARAM(addr_width_p)
    , parameter `BSG_INV_PARAM(data_width_p)
    , parameter `BSG_INV_PARAM(y_cord_width_p)
    , parameter `BSG_INV_PARAM(x_cord_width_p)

    , parameter packet_width_lp =
      `bsg_manycore_packet_width(addr_width_p,data_width_p,
        x_cord_width_p,y_cord_width_p)

    , parameter max_nbf_p = 2**18
    , parameter nbf_addr_width_lp = `BSG_SAFE_CLOG2(max_nbf_p)

    , parameter max_out_credits_p=200
    , parameter credit_counter_width_lp=`BSG_WIDTH(max_out_credits_p)
    , parameter verbose_p = 0

    , parameter uptime_p=0
  )
  ( 
    input clk_i
    , input reset_i
    , output done_o

    , output [packet_width_lp-1:0] packet_o
    , output logic v_o
    , input ready_i

    , input [y_cord_width_p-1:0] my_y_i
    , input [x_cord_width_p-1:0] my_x_i

    , input [credit_counter_width_lp-1:0] out_credits_used_i
  );

  // manycore packet
  //
  typedef struct packed {
    logic [7:0] x_cord;
    logic [7:0] y_cord;
    logic [31:0] epa;
    logic [31:0] data;
  } bsg_nbf_s;

  `declare_bsg_manycore_packet_s(addr_width_p,data_width_p,
    x_cord_width_p,y_cord_width_p);

  bsg_manycore_packet_s packet;

  assign packet_o = packet;



  // read nbf file.
  //
  logic [79:0] nbf [max_nbf_p-1:0];
  logic [nbf_addr_width_lp-1:0] nbf_addr_r, nbf_addr_n;
  bsg_nbf_s curr_nbf;
  assign curr_nbf = nbf[nbf_addr_r];

  assign packet.addr = curr_nbf.epa[0+:addr_width_p];
  assign packet.op_v2 = e_remote_store;
  assign packet.payload = curr_nbf.data;
  assign packet.src_y_cord = my_y_i;
  assign packet.src_x_cord = my_x_i;
  assign packet.y_cord = curr_nbf.y_cord[0+:y_cord_width_p];
  assign packet.x_cord = curr_nbf.x_cord[0+:x_cord_width_p];
  assign packet.reg_id.store_mask_s.mask = '1;
  assign packet.reg_id.store_mask_s.unused = 1'b0;

  localparam num_tiles_lp = `BSG_MACHINE_GLOBAL_X * `BSG_MACHINE_GLOBAL_Y;
  string nbf_file;
  initial begin : load_image
    string count_arg;
    int unsigned iterations;
    int tile;
    bsg_nbf_s entry;
    bit [num_tiles_lp-1:0] patched, released;
    bit terminated, fenced;

    if (!$value$plusargs("iterations=%s", count_arg) || count_arg.len() == 0)
      $fatal(1, "Missing +iterations");
    iterations = 0;
    for (int i = 0; i < count_arg.len(); i++) begin
      if (count_arg.getc(i) < "0" || count_arg.getc(i) > "9")
        $fatal(1, "Invalid +iterations: expected an integer from 1 to 1000000");
      iterations = iterations * 10 + int'(count_arg.getc(i)) - 48;
      if (iterations > 1000000)
        $fatal(1, "Invalid +iterations: expected an integer from 1 to 1000000");
    end
    if (iterations == 0)
      $fatal(1, "Invalid +iterations: expected an integer from 1 to 1000000");
    if (!$value$plusargs("nbf_file=%s", nbf_file))
      $fatal(1, "Missing +nbf_file");
    $readmemh(nbf_file, nbf);

    // The linker reserves byte address 8 (word EPA 2) in each tile's DMEM,
    // after the two interrupt words. Patch the image before the normal loader
    // sends any packets; its credit fence completes these writes before unfreeze.
    patched = '0;
    released = '0;
    terminated = 0;
    fenced = 0;
    for (int i = 0; i < max_nbf_p; i++) begin
      entry = nbf[i];
      if (&entry) begin
        terminated = 1;
        break;
      end
      if (&entry.x_cord && &entry.y_cord && entry.epa == 0 && entry.data == 0) begin
        fenced = 1;
        continue;
      end
      if (int'(entry.x_cord) >= `BSG_MACHINE_ORIGIN_X_CORD
          && int'(entry.x_cord) < `BSG_MACHINE_ORIGIN_X_CORD + `BSG_MACHINE_GLOBAL_X
          && int'(entry.y_cord) >= `BSG_MACHINE_ORIGIN_Y_CORD
          && int'(entry.y_cord) < `BSG_MACHINE_ORIGIN_Y_CORD + `BSG_MACHINE_GLOBAL_Y) begin
        tile = (int'(entry.y_cord) - `BSG_MACHINE_ORIGIN_Y_CORD) * `BSG_MACHINE_GLOBAL_X
               + int'(entry.x_cord) - `BSG_MACHINE_ORIGIN_X_CORD;
        if (entry.epa == 32'h8000 && entry.data == 0) begin
          if (!(&patched) || !fenced || released[tile])
            $fatal(1, "Invalid NBF: tile release before iteration patch/fence or duplicate release");
          released[tile] = 1;
          continue;
        end
        if (entry.epa == 2) begin
          if (patched[tile] || entry.data != 32'h48424954)
            $fatal(1, "Invalid NBF: duplicate or missing iteration marker");
          patched[tile] = 1;
          entry.data = iterations;
          nbf[i] = entry;
        end
      end
      if (|released)
        $fatal(1, "Invalid NBF: memory write after tile release");
      fenced = 0;
    end
    if (!terminated || !(&patched) || !(&released))
      $fatal(1, "Invalid NBF: incomplete iteration patch, tile release, or terminator");
    $display("HammerBlade iterations: %0d (patched %0d tiles)", iterations, num_tiles_lp);
  end

  always @(posedge clk_i)
    if (!reset_i && !done_o && nbf_addr_r == max_nbf_p-1)
      $fatal(1, "NBF exceeds loader capacity or has no terminator");

  logic loader_done_r, loader_done_n;
  assign done_o = loader_done_r;

  // the last line in nbf should be "ff ff ffffffff ffffffff".
  wire is_finish = &curr_nbf; 
  // fence should be "ff ff 00000000 00000000"
  // fence waits until the credits are fully restored.
  wire is_fence = (&curr_nbf.x_cord) & (&curr_nbf.y_cord) & (curr_nbf.epa == '0) & (curr_nbf.data == '0);
 
  always_comb begin
    if (reset_i) begin
      v_o = 1'b0;
      nbf_addr_n = nbf_addr_r;
      loader_done_n = 1'b0;
    end
    else begin
      if (is_finish) begin 
        v_o = 1'b0;
        nbf_addr_n = nbf_addr_r;
        loader_done_n = 1'b1;
      end
      else if (is_fence) begin
        v_o = 1'b0;
        nbf_addr_n = (out_credits_used_i == '0)
          ? nbf_addr_r + 1
          : nbf_addr_r;
        loader_done_n = 1'b0;
      end
      else begin
        v_o = 1'b1;
        nbf_addr_n = ready_i
          ? nbf_addr_r + 1
          : nbf_addr_r;
        loader_done_n = 1'b0;
      end
    end
  end
  
  wire loader_done = ~loader_done_r & loader_done_n;


  // get uptime from /proc/uptime
  function string get_uptime();
    string uptime;
    if (uptime_p) begin
      int fd;
      fd = $fopen("/proc/uptime", "r");
      void'($fscanf(fd, "%s", uptime));
      $fclose(fd);
    end
    return uptime;
  endfunction



  always_ff @ (negedge clk_i) begin
    if (~reset_i) begin
      if (loader_done)
        $display("[BSG_INFO][SPMD_LOADER] SPMD loader finished loading. sim_time=%0t, wall_time=%s", $time, get_uptime());
  
      if (v_o & ready_i & (verbose_p | (nbf_addr_r[9:0] == '0)))
        $display("[BSG_INFO][SPMD_LOADER] sending packet #%0d. x,y=%0d,%0d, addr=%x, data=%x, t=%0t",
          nbf_addr_r,
          packet.x_cord, packet.y_cord,
          packet.addr,
          packet.payload,
          $time
        );
    end
  end
 

  // sequential
  //
  always_ff @ (posedge clk_i) begin
    if (reset_i) begin
      nbf_addr_r <= '0;
      loader_done_r <= 1'b0;
    end
    else begin
      nbf_addr_r <= nbf_addr_n;
      loader_done_r <= loader_done_n;
    end
  end

endmodule

`BSG_ABSTRACT_MODULE(bsg_nonsynth_manycore_spmd_loader)

