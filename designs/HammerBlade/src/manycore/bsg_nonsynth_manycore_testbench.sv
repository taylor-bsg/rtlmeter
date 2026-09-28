/**
 *    bsg_nonsynth_manycore_testbench.v
 *
 */

`include "bsg_manycore_defines.svh"
`include "bsg_cache.svh"

module bsg_nonsynth_manycore_testbench
  import bsg_noc_pkg::*; // {P=0, W, E, N, S}
  import bsg_tag_pkg::*;
  import bsg_cache_pkg::*;
  import bsg_manycore_pkg::*;
  import bsg_manycore_mem_cfg_pkg::*;
  import bsg_manycore_network_cfg_pkg::*;
  #(parameter `BSG_INV_PARAM(num_pods_x_p)
    , parameter `BSG_INV_PARAM(num_pods_y_p)
    , parameter `BSG_INV_PARAM(num_tiles_x_p)
    , parameter `BSG_INV_PARAM(num_tiles_y_p)
    , parameter `BSG_INV_PARAM(x_cord_width_p)
    , parameter `BSG_INV_PARAM(y_cord_width_p)
    , parameter `BSG_INV_PARAM(pod_x_cord_width_p)
    , parameter `BSG_INV_PARAM(pod_y_cord_width_p)
    , parameter `BSG_INV_PARAM(addr_width_p)
    , parameter `BSG_INV_PARAM(data_width_p)
    , parameter `BSG_INV_PARAM(dmem_size_p)
    , parameter `BSG_INV_PARAM(icache_entries_p)
    , parameter `BSG_INV_PARAM(icache_tag_width_p)
    , parameter `BSG_INV_PARAM(icache_block_size_in_words_p)
    , parameter `BSG_INV_PARAM(ruche_factor_X_p)
    , parameter `BSG_INV_PARAM(barrier_ruche_factor_X_p)

    , parameter `BSG_INV_PARAM(num_subarray_x_p)
    , parameter `BSG_INV_PARAM(num_subarray_y_p)

    , parameter `BSG_INV_PARAM(vcache_data_width_p)
    , parameter `BSG_INV_PARAM(vcache_sets_p)
    , parameter `BSG_INV_PARAM(vcache_ways_p)
    , parameter `BSG_INV_PARAM(vcache_block_size_in_words_p) // in words
    , parameter `BSG_INV_PARAM(vcache_dma_data_width_p) // in bits
    , parameter `BSG_INV_PARAM(vcache_size_p) // in words
    , parameter `BSG_INV_PARAM(vcache_addr_width_p) // byte addr
    , parameter `BSG_INV_PARAM(num_vcaches_per_channel_p)
    , parameter `BSG_INV_PARAM(vcache_word_tracking_p)
    , parameter `BSG_INV_PARAM(ipoly_hashing_p)

    , parameter `BSG_INV_PARAM(wh_flit_width_p)
    , parameter wh_ruche_factor_p = 2
    , parameter `BSG_INV_PARAM(wh_cid_width_p)
    , parameter `BSG_INV_PARAM(wh_len_width_p)
    , parameter `BSG_INV_PARAM(wh_cord_width_p)

    , parameter bsg_manycore_network_cfg_e bsg_manycore_network_cfg_p = e_network_half_ruche_x
    , parameter bsg_manycore_mem_cfg_e bsg_manycore_mem_cfg_p = e_vcache_test_mem
    , parameter `BSG_INV_PARAM(bsg_dram_size_p) // in word
    , parameter reset_depth_p = 3

    , parameter enable_vcore_profiling_p=0
    , parameter enable_router_profiling_p=0
    , parameter enable_cache_profiling_p=0
    , parameter enable_vanilla_core_trace_p = 0
    , parameter enable_remote_op_profiling_p = 0

    , parameter enable_vcore_pc_coverage_p=0

    , parameter enable_vanilla_core_pc_histogram_p=0

    , parameter cache_bank_addr_width_lp = `BSG_SAFE_CLOG2(bsg_dram_size_p/(2*num_tiles_x_p)*4) // byte addr
    , parameter link_sif_width_lp =
      `bsg_manycore_link_sif_width(addr_width_p,data_width_p,x_cord_width_p,y_cord_width_p)

    // This is used to define heterogeneous arrays. Each index defines
    // the type of an X/Y coordinate in the array. This is a vector of
    // num_tiles_x_p*num_tiles_y_p ints; type "0" is the
    // default. See bsg_manycore_hetero_socket.v for more types.
    , parameter int hetero_type_vec_p [0:(num_tiles_y_p*num_tiles_x_p) - 1]  = '{default:0}
  )
  (
    input clk_i
    , input reset_i

    , input dram_clk_i

    , output tag_done_o
    
    , input  [link_sif_width_lp-1:0] io_link_sif_i
    , output [link_sif_width_lp-1:0] io_link_sif_o
  );


  // print machine settings
  initial begin
    $display("MACHINE SETTINGS:");
    $display("[INFO][TESTBENCH] BSG_MACHINE_GLOBAL_X                 = %d", num_tiles_x_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_GLOBAL_Y                 = %d", num_tiles_y_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_VCACHE_SET               = %d", vcache_sets_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_VCACHE_WAY               = %d", vcache_ways_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_VCACHE_BLOCK_SIZE_WORDS  = %d", vcache_block_size_in_words_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_MAX_EPA_WIDTH            = %d", addr_width_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_MEM_CFG                  = %s", bsg_manycore_mem_cfg_p.name());
    $display("[INFO][TESTBENCH] BSG_MACHINE_NETWORK_CFG              = %s", bsg_manycore_network_cfg_p.name());
    $display("[INFO][TESTBENCH] BSG_MACHINE_RUCHE_FACTOR_X           = %d", ruche_factor_X_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_BARRIER_RUCHE_FACTOR_X   = %d", barrier_ruche_factor_X_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_SUBARRAY_X               = %d", num_subarray_x_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_SUBARRAY_Y               = %d", num_subarray_y_p);
    $display("[INFO][TESTBENCH] BSG_MACHINE_ORIGIN_X_CORD            = %d", `BSG_MACHINE_ORIGIN_X_CORD);
    $display("[INFO][TESTBENCH] BSG_MACHINE_ORIGIN_Y_CORD            = %d", `BSG_MACHINE_ORIGIN_Y_CORD);
    $display("[INFO][TESTBENCH] vcache_word_tracking_p               = %d", vcache_word_tracking_p);
    $display("[INFO][TESTBENCH] ipoly_hashing_p                      = %d", ipoly_hashing_p);
    $display("[INFO][TESTBENCH] enable_vcore_profiling_p             = %d", enable_vcore_profiling_p);
    $display("[INFO][TESTBENCH] enable_router_profiling_p            = %d", enable_router_profiling_p);
    $display("[INFO][TESTBENCH] enable_cache_profiling_p             = %d", enable_cache_profiling_p);
    $display("[INFO][TESTBENCH] enable_vcore_pc_coverage_p           = %d", enable_vcore_pc_coverage_p);
  end


  // BSG TAG MASTER
  logic tag_done_lo;
  bsg_tag_s [num_pods_y_p-1:0][num_pods_x_p-1:0] pod_tags_lo;

  bsg_nonsynth_manycore_tag_master #(
    .num_pods_x_p(num_pods_x_p)
    ,.num_pods_y_p(num_pods_y_p)
    ,.wh_cord_width_p(wh_cord_width_p)
  ) mtm (
    .clk_i(clk_i)
    ,.reset_i(reset_i)
    
    ,.tag_done_o(tag_done_lo)
    ,.pod_tags_o(pod_tags_lo)
  );   
  
  assign tag_done_o = tag_done_lo;

  // deassert reset when tag programming is done.
  wire reset = ~tag_done_lo;
  logic reset_r, reset_delayed;
  assign reset_r = ~tag_done_lo | reset_delayed;
  bsg_dff_chain #(
    .width_p(1)
    ,.num_stages_p(reset_depth_p)
  ) reset_dff (
    .clk_i(clk_i)
    ,.data_i(reset)
    ,.data_o(reset_delayed)
  );

  logic dram_reset_r;
  bsg_sync_sync #(.width_p(1)) dram_reset_bss (
    .oclk_i(dram_clk_i)
    ,.iclk_data_i(reset_r)
    ,.oclk_data_o(dram_reset_r)
  );


  // instantiate manycore
  `declare_bsg_manycore_link_sif_s(addr_width_p,data_width_p,x_cord_width_p,y_cord_width_p);
  `declare_bsg_manycore_ruche_x_link_sif_s(addr_width_p,data_width_p,x_cord_width_p,y_cord_width_p);
  `declare_bsg_ready_and_link_sif_s(wh_flit_width_p, wh_link_sif_s);
  bsg_manycore_link_sif_s [S:N][(num_pods_x_p*num_tiles_x_p)-1:0] ver_link_sif_li;
  bsg_manycore_link_sif_s [S:N][(num_pods_x_p*num_tiles_x_p)-1:0] ver_link_sif_lo;
  wh_link_sif_s [E:W][num_pods_y_p-1:0][S:N][wh_ruche_factor_p-1:0] wh_link_sif_li;
  wh_link_sif_s [E:W][num_pods_y_p-1:0][S:N][wh_ruche_factor_p-1:0] wh_link_sif_lo;
  bsg_manycore_link_sif_s [E:W][num_pods_y_p-1:0][num_tiles_y_p-1:0] hor_link_sif_li;
  bsg_manycore_link_sif_s [E:W][num_pods_y_p-1:0][num_tiles_y_p-1:0] hor_link_sif_lo;
  bsg_manycore_ruche_x_link_sif_s [E:W][num_pods_y_p-1:0][num_tiles_y_p-1:0] ruche_link_li;
  bsg_manycore_ruche_x_link_sif_s [E:W][num_pods_y_p-1:0][num_tiles_y_p-1:0] ruche_link_lo;

  if (bsg_manycore_network_cfg_p == e_network_half_ruche_x) begin: fi1
    bsg_manycore_pod_ruche_array #(
      .num_tiles_x_p(num_tiles_x_p)
      ,.num_tiles_y_p(num_tiles_y_p)
      ,.pod_x_cord_width_p(pod_x_cord_width_p)
      ,.pod_y_cord_width_p(pod_y_cord_width_p)
      ,.x_cord_width_p(x_cord_width_p)
      ,.y_cord_width_p(y_cord_width_p)
      ,.addr_width_p(addr_width_p)
      ,.data_width_p(data_width_p)
      ,.ruche_factor_X_p(ruche_factor_X_p)
      ,.barrier_ruche_factor_X_p(barrier_ruche_factor_X_p)
      ,.num_subarray_x_p(num_subarray_x_p)
      ,.num_subarray_y_p(num_subarray_y_p)

      ,.dmem_size_p(dmem_size_p)
      ,.icache_entries_p(icache_entries_p)
      ,.icache_tag_width_p(icache_tag_width_p)
      ,.icache_block_size_in_words_p(icache_block_size_in_words_p)

      ,.vcache_addr_width_p(vcache_addr_width_p)
      ,.vcache_data_width_p(vcache_data_width_p)
      ,.vcache_ways_p(vcache_ways_p)
      ,.vcache_sets_p(vcache_sets_p)
      ,.vcache_block_size_in_words_p(vcache_block_size_in_words_p)
      ,.vcache_size_p(vcache_size_p)
      ,.vcache_dma_data_width_p(vcache_dma_data_width_p)
      ,.vcache_word_tracking_p(vcache_word_tracking_p)
      ,.ipoly_hashing_p(ipoly_hashing_p)

      ,.wh_ruche_factor_p(wh_ruche_factor_p)
      ,.wh_cid_width_p(wh_cid_width_p)
      ,.wh_flit_width_p(wh_flit_width_p)
      ,.wh_cord_width_p(wh_cord_width_p)
      ,.wh_len_width_p(wh_len_width_p)

      ,.num_pods_y_p(num_pods_y_p)
      ,.num_pods_x_p(num_pods_x_p)

      ,.reset_depth_p(reset_depth_p)
      ,.hetero_type_vec_p(hetero_type_vec_p)
    ) DUT (
      .clk_i(clk_i)

      ,.ver_link_sif_i(ver_link_sif_li)
      ,.ver_link_sif_o(ver_link_sif_lo)

      ,.wh_link_sif_i(wh_link_sif_li)
      ,.wh_link_sif_o(wh_link_sif_lo)

      ,.hor_link_sif_i(hor_link_sif_li)
      ,.hor_link_sif_o(hor_link_sif_lo)

      ,.ruche_link_i(ruche_link_li)
      ,.ruche_link_o(ruche_link_lo)

      ,.pod_tags_i(pod_tags_lo) 
    );
  end
  else if (bsg_manycore_network_cfg_p == e_network_mesh) begin: fi1
    bsg_manycore_pod_mesh_array #(
      .num_tiles_x_p(num_tiles_x_p)
      ,.num_tiles_y_p(num_tiles_y_p)
      ,.pod_x_cord_width_p(pod_x_cord_width_p)
      ,.pod_y_cord_width_p(pod_y_cord_width_p)
      ,.x_cord_width_p(x_cord_width_p)
      ,.y_cord_width_p(y_cord_width_p)
      ,.addr_width_p(addr_width_p)
      ,.data_width_p(data_width_p)
      ,.barrier_ruche_factor_X_p(barrier_ruche_factor_X_p)
      ,.num_subarray_x_p(num_subarray_x_p)
      ,.num_subarray_y_p(num_subarray_y_p)

      ,.dmem_size_p(dmem_size_p)
      ,.icache_entries_p(icache_entries_p)
      ,.icache_tag_width_p(icache_tag_width_p)
      ,.icache_block_size_in_words_p(icache_block_size_in_words_p)

      ,.vcache_addr_width_p(vcache_addr_width_p)
      ,.vcache_data_width_p(vcache_data_width_p)
      ,.vcache_ways_p(vcache_ways_p)
      ,.vcache_sets_p(vcache_sets_p)
      ,.vcache_block_size_in_words_p(vcache_block_size_in_words_p)
      ,.vcache_size_p(vcache_size_p)
      ,.vcache_dma_data_width_p(vcache_dma_data_width_p)
      ,.vcache_word_tracking_p(vcache_word_tracking_p)
      ,.ipoly_hashing_p(ipoly_hashing_p)

      ,.wh_ruche_factor_p(wh_ruche_factor_p)
      ,.wh_cid_width_p(wh_cid_width_p)
      ,.wh_flit_width_p(wh_flit_width_p)
      ,.wh_cord_width_p(wh_cord_width_p)
      ,.wh_len_width_p(wh_len_width_p)

      ,.num_pods_y_p(num_pods_y_p)
      ,.num_pods_x_p(num_pods_x_p)

      ,.reset_depth_p(reset_depth_p)
      ,.hetero_type_vec_p(hetero_type_vec_p)
    ) DUT (
      .clk_i(clk_i)

      ,.ver_link_sif_i(ver_link_sif_li)
      ,.ver_link_sif_o(ver_link_sif_lo)

      ,.wh_link_sif_i(wh_link_sif_li)
      ,.wh_link_sif_o(wh_link_sif_lo)

      ,.hor_link_sif_i(hor_link_sif_li)
      ,.hor_link_sif_o(hor_link_sif_lo)

      ,.pod_tags_i(pod_tags_lo) 
    );
  end
  else begin
    initial begin
      $error("Invalid bsg_manycore_network_cfg_p.");
    end
  end

  // Invert WH ruche links
  // hardcoded for ruche factor = 2
  wh_link_sif_s [E:W][num_pods_y_p-1:0][S:N][wh_ruche_factor_p-1:0] buffered_wh_link_sif_li,
                                                                    buffered_wh_link_sif_lo;
  for (genvar i = W; i <= E; i++) begin
    for (genvar j = 0; j < num_pods_y_p; j++) begin
      for (genvar k = N; k <= S; k++) begin
        for (genvar r = 0; r < wh_ruche_factor_p; r++) begin
          if (r == 0) begin
            assign wh_link_sif_li[i][j][k][r] = buffered_wh_link_sif_li[i][j][k][r];
            assign buffered_wh_link_sif_lo[i][j][k][r] = wh_link_sif_lo[i][j][k][r];
          end
          else begin
            assign wh_link_sif_li[i][j][k][r] = ~buffered_wh_link_sif_li[i][j][k][r];
            assign buffered_wh_link_sif_lo[i][j][k][r] = ~wh_link_sif_lo[i][j][k][r];
          end
        end
      end
    end
  end

  // IO ROUTER
  localparam rev_use_credits_lp = 5'b00001;
  localparam int rev_fifo_els_lp[4:0] = '{2,2,2,2,3};
  bsg_manycore_link_sif_s [(num_pods_x_p*num_tiles_x_p)-1:0][S:P] io_link_sif_li;
  bsg_manycore_link_sif_s [(num_pods_x_p*num_tiles_x_p)-1:0][S:P] io_link_sif_lo;

  for (genvar x = 0; x < num_pods_x_p*num_tiles_x_p; x++) begin: io_rtr_x
    bsg_manycore_mesh_node #(
      .x_cord_width_p(x_cord_width_p)
      ,.y_cord_width_p(y_cord_width_p)
      ,.addr_width_p(addr_width_p)
      ,.data_width_p(data_width_p)
      ,.stub_p(4'b0100) // stub north
      ,.rev_use_credits_p(rev_use_credits_lp)
      ,.rev_fifo_els_p(rev_fifo_els_lp)
    ) io_rtr (
      .clk_i(clk_i)
      ,.reset_i(reset_r)

      ,.links_sif_i(io_link_sif_li[x][S:W])
      ,.links_sif_o(io_link_sif_lo[x][S:W])

      ,.proc_link_sif_i(io_link_sif_li[x][P])
      ,.proc_link_sif_o(io_link_sif_lo[x][P])

      // The first pod starts at 2^local_X_bits; SAFE_CLOG2 reserves one bit even for X=1.
      // Add the column index to that origin, placing the single-column I/O router at X=2.
      // Multiple pods across X are unsupported when each pod is only one tile wide.
      // They require I/O X coordinates 2,4,..., but this formula produces 2,3,... .
      ,.global_x_i(x_cord_width_p'((1 << `BSG_SAFE_CLOG2(num_tiles_x_p))+x))
      ,.global_y_i(y_cord_width_p'(0))
    );

    // connect to pod array
    assign ver_link_sif_li[N][x] = io_link_sif_lo[x][S];
    assign io_link_sif_li[x][S] = ver_link_sif_lo[N][x];

    // connect between io rtr
    if (x < (num_pods_x_p*num_tiles_x_p)-1) begin
      assign io_link_sif_li[x][E] = io_link_sif_lo[x+1][W];
      assign io_link_sif_li[x+1][W] = io_link_sif_lo[x][E];
    end
  end



  // Host link connection
  assign io_link_sif_li[0][P] = io_link_sif_i;
  assign io_link_sif_o = io_link_sif_lo[0][P];




  //                              //
  // Configurable Memory System   //
  //                              //
  localparam logic [e_max_val-1:0] mem_cfg_lp = (1 << bsg_manycore_mem_cfg_p);

  if (mem_cfg_lp[e_vcache_test_mem]) begin: test_mem
    // in bytes
    // north + south row of vcache
    localparam longint unsigned mem_size_lp = (2**30)*num_pods_x_p/wh_ruche_factor_p/2;
    localparam num_vcaches_per_test_mem_lp = (num_tiles_x_p*num_pods_x_p)/wh_ruche_factor_p/2;

    for (genvar i = W; i <= E; i++) begin: hs                           // horizontal side
      for (genvar j = 0; j < num_pods_y_p; j++) begin: py               // pod y
        for (genvar k = N; k <= S; k++) begin: vs                       // vertical side
          for (genvar r = 0; r < wh_ruche_factor_p; r++) begin: rf    // ruching
            bsg_nonsynth_wormhole_test_mem #(
              .vcache_data_width_p(vcache_data_width_p)
              ,.vcache_dma_data_width_p(vcache_dma_data_width_p)
              ,.vcache_block_size_in_words_p(vcache_block_size_in_words_p)
              ,.num_vcaches_p(num_vcaches_per_test_mem_lp)
              ,.wh_cid_width_p(wh_cid_width_p)
              ,.wh_flit_width_p(wh_flit_width_p)
              ,.wh_cord_width_p(wh_cord_width_p)
              ,.wh_len_width_p(wh_len_width_p)
              ,.wh_ruche_factor_p(wh_ruche_factor_p)
              ,.no_concentration_p(1)
              ,.mem_size_p(mem_size_lp)
            ) test_mem (
              .clk_i(clk_i)
              ,.reset_i(reset_r)

              ,.wh_link_sif_i(buffered_wh_link_sif_lo[i][j][k][r])
              ,.wh_link_sif_o(buffered_wh_link_sif_li[i][j][k][r])
            );
          end
        end
      end
    end

  end
  else begin: unsupported_memory
    initial $fatal(1, "RTLmeter HammerBlade requires e_vcache_test_mem");
  end

  // IO P tie off
  for (genvar i = 1; i < num_pods_x_p*num_tiles_x_p; i++) begin
    bsg_manycore_link_sif_tieoff #(
      .addr_width_p(addr_width_p)
      ,.data_width_p(data_width_p)
      ,.x_cord_width_p(x_cord_width_p)
      ,.y_cord_width_p(y_cord_width_p)
    ) io_p_tieoff (
      .clk_i(clk_i)
      ,.reset_i(reset_r)
      ,.link_sif_i(io_link_sif_lo[i][P])
      ,.link_sif_o(io_link_sif_li[i][P])
    );
  end

  // IO west end tieoff
  bsg_manycore_link_sif_tieoff #(
    .addr_width_p(addr_width_p)
    ,.data_width_p(data_width_p)
    ,.x_cord_width_p(x_cord_width_p)
    ,.y_cord_width_p(y_cord_width_p)
  ) io_w_tieoff (
    .clk_i(clk_i)
    ,.reset_i(reset_r)
    ,.link_sif_i(io_link_sif_lo[0][W])
    ,.link_sif_o(io_link_sif_li[0][W])
  );

  // IO east end tieoff
  bsg_manycore_link_sif_tieoff #(
    .addr_width_p(addr_width_p)
    ,.data_width_p(data_width_p)
    ,.x_cord_width_p(x_cord_width_p)
    ,.y_cord_width_p(y_cord_width_p)
  ) io_e_tieoff (
    .clk_i(clk_i)
    ,.reset_i(reset_r)
    ,.link_sif_i(io_link_sif_lo[(num_pods_x_p*num_tiles_x_p)-1][E])
    ,.link_sif_o(io_link_sif_li[(num_pods_x_p*num_tiles_x_p)-1][E])
  );


  // SOUTH VER LINK TIE OFFS
  for (genvar i = 0; i < num_pods_x_p*num_tiles_x_p; i++) begin
    bsg_manycore_link_sif_tieoff #(
      .addr_width_p(addr_width_p)
      ,.data_width_p(data_width_p)
      ,.x_cord_width_p(x_cord_width_p)
      ,.y_cord_width_p(y_cord_width_p)
    ) ver_s_tieoff (
      .clk_i(clk_i)
      ,.reset_i(reset_r)
      ,.link_sif_i(ver_link_sif_lo[S][i])
      ,.link_sif_o(ver_link_sif_li[S][i])
    );
  end


  // HOR TIEOFF (local link)
  for (genvar i = W; i <= E; i++) begin
    for (genvar j = 0; j < num_pods_y_p; j++) begin
      for (genvar k = 0; k < num_tiles_y_p; k++) begin
        bsg_manycore_link_sif_tieoff #(
          .addr_width_p(addr_width_p)
          ,.data_width_p(data_width_p)
          ,.x_cord_width_p(x_cord_width_p)
          ,.y_cord_width_p(y_cord_width_p)
        ) hor_tieoff (
          .clk_i(clk_i)
          ,.reset_i(reset_r)
          ,.link_sif_i(hor_link_sif_lo[i][j][k])
          ,.link_sif_o(hor_link_sif_li[i][j][k])
        );
      end
    end
  end


  // RUCHE LINK TIEOFF (west)
  for (genvar j = 0; j < num_pods_y_p; j++) begin
    for (genvar k = 0; k < num_tiles_y_p; k++) begin
      // if ruche factor is even, tieoff with '1
      // if ruche factor is odd,  tieoff with '0
      assign ruche_link_li[W][j][k] = (ruche_factor_X_p%2 == 0) ? '1 : '0;
    end
  end

  // RUCHE LINK TIEOFF (east)
  for (genvar j = 0; j < num_pods_y_p; j++) begin
    for (genvar k = 0; k < num_tiles_y_p; k++) begin
      // always tieoff with '0;
      assign ruche_link_li[E][j][k] = '0;
    end
  end
  








//                  //
//    PROFILERS     //
//                  //

endmodule

`BSG_ABSTRACT_MODULE(bsg_nonsynth_manycore_testbench)
