var _slicedToArray = function () { function sliceIterator(arr, i) { var _arr = []; var _n = true; var _d = false; var _e = undefined; try { for (var _i = arr[Symbol.iterator](), _s; !(_n = (_s = _i.next()).done); _n = true) { _arr.push(_s.value); if (i && _arr.length === i) break; } } catch (err) { _d = true; _e = err; } finally { try { if (!_n && _i["return"]) _i["return"](); } finally { if (_d) throw _e; } } return _arr; } return function (arr, i) { if (Array.isArray(arr)) { return arr; } else if (Symbol.iterator in Object(arr)) { return sliceIterator(arr, i); } else { throw new TypeError("Invalid attempt to destructure non-iterable instance"); } }; }();

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

function Square(props) {
  return React.createElement(
    "button",
    { className: "square", onClick: props.onClick },
    props.value
  );
}

var Board = function (_React$Component) {
  _inherits(Board, _React$Component);

  function Board() {
    _classCallCheck(this, Board);

    return _possibleConstructorReturn(this, (Board.__proto__ || Object.getPrototypeOf(Board)).apply(this, arguments));
  }

  _createClass(Board, [{
    key: "renderSquare",
    value: function renderSquare(i) {
      var _this2 = this;

      return React.createElement(Square, { value: this.props.squares[i], onClick: function onClick() {
          return _this2.props.onClick(i);
        } });
    }
  }, {
    key: "render",
    value: function render() {
      return React.createElement(
        "div",
        null,
        React.createElement(
          "div",
          { className: "board-row" },
          this.renderSquare(0),
          this.renderSquare(1),
          this.renderSquare(2)
        ),
        React.createElement(
          "div",
          { className: "board-row" },
          this.renderSquare(3),
          this.renderSquare(4),
          this.renderSquare(5)
        ),
        React.createElement(
          "div",
          { className: "board-row" },
          this.renderSquare(6),
          this.renderSquare(7),
          this.renderSquare(8)
        )
      );
    }
  }]);

  return Board;
}(React.Component);

var Game = function (_React$Component2) {
  _inherits(Game, _React$Component2);

  function Game(props) {
    _classCallCheck(this, Game);

    var _this3 = _possibleConstructorReturn(this, (Game.__proto__ || Object.getPrototypeOf(Game)).call(this, props));

    _this3.state = {
      history: [{
        squares: Array(9).fill(null)
      }],
      stepNumber: 0,
      xIsNext: true
    };
    return _this3;
  }

  _createClass(Game, [{
    key: "handleClick",
    value: function handleClick(i) {
      var history = this.state.history.slice(0, this.state.stepNumber + 1);
      var current = history[history.length - 1];
      var squares = current.squares.slice();
      if (calculateWinner(squares) || squares[i]) {
        return;
      }
      squares[i] = this.state.xIsNext ? 'X' : 'O';
      this.setState({
        history: history.concat([{ squares: squares }]),
        stepNumber: history.length,
        xIsNext: !this.state.xIsNext
      });
    }
  }, {
    key: "jumpTo",
    value: function jumpTo(step) {
      this.setState({
        stepNumber: step,
        xIsNext: step % 2 === 0
      });
    }
  }, {
    key: "render",
    value: function render() {
      var _this4 = this;

      var history = this.state.history;
      var current = history[this.state.stepNumber];
      var winner = calculateWinner(current.squares);

      var moves = history.map(function (step, move) {
        var desc = move ? 'Go to move #' + move : 'Go to game start';
        return React.createElement(
          "li",
          { key: move },
          React.createElement(
            "button",
            { onClick: function onClick() {
                return _this4.jumpTo(move);
              } },
            desc
          )
        );
      });

      var status = void 0;
      if (winner) {
        status = 'Winner: ' + winner;
      } else {
        status = 'Next Player: ' + (this.state.xIsNext ? 'X' : 'O');
      }

      return React.createElement(
        "div",
        { className: "game" },
        React.createElement(
          "div",
          { className: "game-board" },
          React.createElement(Board, { squares: current.squares, onClick: function onClick(i) {
              return _this4.handleClick(i);
            } })
        ),
        React.createElement(
          "div",
          { className: "game-info" },
          React.createElement(
            "div",
            null,
            status
          ),
          React.createElement(
            "ol",
            null,
            moves
          )
        )
      );
    }
  }]);

  return Game;
}(React.Component);

// ========================================

ReactDOM.render(React.createElement(Game, null), document.getElementById('root'));

function calculateWinner(squares) {
  var lines = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]];
  for (var i = 0; i < lines.length; i++) {
    var _lines$i = _slicedToArray(lines[i], 3),
        a = _lines$i[0],
        b = _lines$i[1],
        c = _lines$i[2];

    if (squares[a] && squares[a] === squares[b] && squares[a] === squares[c]) {
      return squares[a];
    }
  }
  return null;
}

var ProductCategoryRow = function (_React$Component3) {
  _inherits(ProductCategoryRow, _React$Component3);

  function ProductCategoryRow() {
    _classCallCheck(this, ProductCategoryRow);

    return _possibleConstructorReturn(this, (ProductCategoryRow.__proto__ || Object.getPrototypeOf(ProductCategoryRow)).apply(this, arguments));
  }

  _createClass(ProductCategoryRow, [{
    key: "render",
    value: function render() {
      var category = this.props.category;
      return React.createElement(
        "tr",
        null,
        React.createElement(
          "th",
          { colSpan: "2" },
          category
        )
      );
    }
  }]);

  return ProductCategoryRow;
}(React.Component);

var ProductRow = function (_React$Component4) {
  _inherits(ProductRow, _React$Component4);

  function ProductRow() {
    _classCallCheck(this, ProductRow);

    return _possibleConstructorReturn(this, (ProductRow.__proto__ || Object.getPrototypeOf(ProductRow)).apply(this, arguments));
  }

  _createClass(ProductRow, [{
    key: "render",
    value: function render() {
      var product = this.props.product;
      var name = product.stocked ? product.name : React.createElement(
        "span",
        { style: { color: 'red' } },
        product.name
      );

      return React.createElement(
        "tr",
        null,
        React.createElement(
          "td",
          null,
          name
        ),
        React.createElement(
          "td",
          null,
          product.price
        )
      );
    }
  }]);

  return ProductRow;
}(React.Component);

var ProductTable = function (_React$Component5) {
  _inherits(ProductTable, _React$Component5);

  function ProductTable() {
    _classCallCheck(this, ProductTable);

    return _possibleConstructorReturn(this, (ProductTable.__proto__ || Object.getPrototypeOf(ProductTable)).apply(this, arguments));
  }

  _createClass(ProductTable, [{
    key: "render",
    value: function render() {
      var filterText = this.props.filterText;
      var inStockOnly = this.props.inStockOnly;

      var rows = [];
      var lastCategory = null;

      this.props.products.forEach(function (product) {
        if (product.name.indexOf(filterText) === -1) {
          return;
        }
        if (inStockOnly && !product.stocked) {
          return;
        }
        if (product.category !== lastCategory) {
          rows.push(React.createElement(ProductCategoryRow, {
            category: product.category,
            key: product.category }));
        }
        rows.push(React.createElement(ProductRow, {
          product: product,
          key: product.name }));
        lastCategory = product.category;
      });

      return React.createElement(
        "table",
        null,
        React.createElement(
          "thead",
          null,
          React.createElement(
            "tr",
            null,
            React.createElement(
              "th",
              null,
              "Name"
            ),
            React.createElement(
              "th",
              null,
              "Price"
            )
          )
        ),
        React.createElement(
          "tbody",
          null,
          rows
        )
      );
    }
  }]);

  return ProductTable;
}(React.Component);

var SearchBar = function (_React$Component6) {
  _inherits(SearchBar, _React$Component6);

  function SearchBar(props) {
    _classCallCheck(this, SearchBar);

    var _this8 = _possibleConstructorReturn(this, (SearchBar.__proto__ || Object.getPrototypeOf(SearchBar)).call(this, props));

    _this8.handleFilterTextChange = _this8.handleFilterTextChange.bind(_this8);
    _this8.handleInStockChange = _this8.handleInStockChange.bind(_this8);
    return _this8;
  }

  _createClass(SearchBar, [{
    key: "handleFilterTextChange",
    value: function handleFilterTextChange(e) {
      this.props.onFilterTextChange(e.target.value);
    }
  }, {
    key: "handleInStockChange",
    value: function handleInStockChange(e) {
      this.props.onInStockChange(e.target.checked);
    }
  }, {
    key: "render",
    value: function render() {
      var filterText = this.props.filterText;
      var inStockOnly = this.props.inStockOnly;

      return React.createElement(
        "form",
        null,
        React.createElement("input", {
          type: "text",
          placeholder: "Search...",
          value: this.props.filterText,
          onChange: this.handleFilterTextChange
        }),
        React.createElement(
          "p",
          null,
          React.createElement("input", {
            type: "checkbox",
            checked: this.props.inStockOnly,
            onChange: this.handleInStockChange
          }),
          ' ',
          "Only show products in stock"
        )
      );
    }
  }]);

  return SearchBar;
}(React.Component);

var FilterableProductTable = function (_React$Component7) {
  _inherits(FilterableProductTable, _React$Component7);

  function FilterableProductTable(props) {
    _classCallCheck(this, FilterableProductTable);

    var _this9 = _possibleConstructorReturn(this, (FilterableProductTable.__proto__ || Object.getPrototypeOf(FilterableProductTable)).call(this, props));

    _this9.state = {
      filterText: '',
      inStockOnly: false
    };

    _this9.handleFilterTextChange = _this9.handleFilterTextChange.bind(_this9);
    _this9.handleInStockChange = _this9.handleInStockChange.bind(_this9);
    return _this9;
  }

  _createClass(FilterableProductTable, [{
    key: "handleFilterTextChange",
    value: function handleFilterTextChange(filterText) {
      this.setState({
        filterText: filterText
      });
    }
  }, {
    key: "handleInStockChange",
    value: function handleInStockChange(inStockOnly) {
      this.setState({
        inStockOnly: inStockOnly
      });
    }
  }, {
    key: "render",
    value: function render() {
      return React.createElement(
        "div",
        null,
        React.createElement(SearchBar, {
          filterText: this.state.filterText,
          inStockOnly: this.state.inStockOnly,
          onFilterTextChange: this.handleFilterTextChange,
          onInStockChange: this.handleInStockChange
        }),
        React.createElement(ProductTable, {
          products: this.props.products,
          filterText: this.state.filterText,
          inStockOnly: this.state.inStockOnly
        })
      );
    }
  }]);

  return FilterableProductTable;
}(React.Component);

var PRODUCTS = [{ category: 'Sporting Goods', price: '$49.99', stocked: true, name: 'Football' }, { category: 'Sporting Goods', price: '$9.99', stocked: true, name: 'Baseball' }, { category: 'Sporting Goods', price: '$29.99', stocked: false, name: 'Basketball' }, { category: 'Electronics', price: '$99.99', stocked: true, name: 'iPod Touch' }, { category: 'Electronics', price: '$399.99', stocked: false, name: 'iPhone 5' }, { category: 'Electronics', price: '$199.99', stocked: true, name: 'Nexus 7' }];

ReactDOM.render(React.createElement(FilterableProductTable, { products: PRODUCTS }), document.getElementById('test'));